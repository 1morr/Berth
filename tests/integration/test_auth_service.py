"""登入、session 與角色（plan §11.1 T0.5、brief §11、票 07）。

身分的來源永遠是 Jellyfin：Berth 不驗證密碼，只把 `Policy.IsAdministrator` 翻成角色，
再發一張自己的 session。這裡測的是那條翻譯與 session 的生命週期；API 的形狀在
`test_auth_api.py`。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.domain import Role
from berth.models import JellyfinSettings, User, UserSession
from berth.services.auth import (
    SESSION_TTL,
    InvalidCredentialsError,
    JellyfinUnavailableError,
    read_session,
    sign_in,
    sign_out,
    token_digest,
)
from berth.services.settings import write_settings

#: 這個檔案裡的每個測試都是非同步的（`asyncio_mode = strict`，見 pyproject）。
pytestmark = pytest.mark.asyncio

JELLYFIN_URL = "http://jellyfin:8096"


class OneJellyfin:
    """所有請求都回同一台 Fake，測試才看得到它被問過什麼。"""

    def __init__(self, jellyfin: FakeJellyfinClient) -> None:
        self._jellyfin = jellyfin
        self.asked: list[str] = []

    def jellyfin(self, base_url: str, token: str = "") -> FakeJellyfinClient:
        self.asked.append(base_url)
        return self._jellyfin

    def qbittorrent(self, base_url: str) -> FakeQbittorrentClient:
        raise AssertionError("login never talks to qBittorrent")

    def prowlarr(self, base_url: str, api_key: str) -> FakeProwlarrClient:
        raise AssertionError("login never talks to Prowlarr")


@pytest.fixture
def jellyfin() -> FakeJellyfinClient:
    """已經跑完初始精靈的一台：管理員是 skipper，另有一個普通使用者。"""
    return FakeJellyfinClient(
        startup_wizard_completed=True,
        admin=("skipper", "harbour"),
        users={"deckhand": "rope"},
    )


@pytest.fixture
def factory(jellyfin: FakeJellyfinClient) -> OneJellyfin:
    return OneJellyfin(jellyfin)


@pytest_asyncio.fixture
async def configured(session: AsyncSession) -> AsyncIterator[None]:
    """精靈跑完後的樣子：Jellyfin 的位址已經存下來了。"""
    await write_settings(session, JellyfinSettings(base_url=JELLYFIN_URL, api_key="key"))
    await session.commit()
    yield


@pytest.mark.usefixtures("configured")
class TestSignIn:
    async def test_a_jellyfin_administrator_becomes_a_berth_admin(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        signed = await sign_in(session, factory, username="skipper", password="harbour")

        assert signed.user.name == "skipper"
        assert signed.user.role is Role.ADMIN

    async def test_an_ordinary_jellyfin_user_becomes_a_berth_user(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        signed = await sign_in(session, factory, username="deckhand", password="rope")

        assert signed.user.role is Role.USER

    async def test_login_talks_to_the_configured_jellyfin(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        await sign_in(session, factory, username="skipper", password="harbour")

        assert factory.asked == [JELLYFIN_URL]

    async def test_the_user_row_mirrors_the_jellyfin_identity(
        self, session: AsyncSession, factory: OneJellyfin, jellyfin: FakeJellyfinClient
    ) -> None:
        """`users` 只是本地鏡射，密碼永遠不在這裡（brief §11）。"""
        signed = await sign_in(session, factory, username="skipper", password="harbour")

        row = await session.get(User, signed.user.id)
        expected = await jellyfin.authenticate("skipper", "harbour")
        assert row is not None
        assert row.jellyfin_user_id == expected.user_id
        assert row.last_login_at is not None

    async def test_signing_in_twice_reuses_the_same_user_row(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        first = await sign_in(session, factory, username="skipper", password="harbour")
        second = await sign_in(session, factory, username="skipper", password="harbour")

        assert first.user.id == second.user.id
        assert await session.scalar(select(func.count()).select_from(User)) == 1

    async def test_a_demotion_in_jellyfin_reaches_berth_on_the_next_login(
        self, session: AsyncSession, factory: OneJellyfin, jellyfin: FakeJellyfinClient
    ) -> None:
        """角色不是存一次就定了：每次登入都重新問 Jellyfin（brief §11）。"""
        await sign_in(session, factory, username="skipper", password="harbour")
        jellyfin.admin = None
        jellyfin.users = {"skipper": "harbour"}

        again = await sign_in(session, factory, username="skipper", password="harbour")

        assert again.user.role is Role.USER

    async def test_two_people_get_two_rows(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        skipper = await sign_in(session, factory, username="skipper", password="harbour")
        deckhand = await sign_in(session, factory, username="deckhand", password="rope")

        assert skipper.user.id != deckhand.user.id


@pytest.mark.usefixtures("configured")
class TestRefusal:
    async def test_a_wrong_password_is_refused(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        with pytest.raises(InvalidCredentialsError):
            await sign_in(session, factory, username="skipper", password="wrong")

    async def test_an_unknown_account_is_refused_the_same_way(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        """訊息不區分「帳號不存在」與「密碼錯誤」（票 07 驗收）。"""
        wrong_password = await _refusal(session, factory, "skipper", "wrong")
        unknown_account = await _refusal(session, factory, "nobody", "harbour")

        assert str(wrong_password) == str(unknown_account)

    async def test_blank_credentials_never_reach_jellyfin(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        with pytest.raises(InvalidCredentialsError):
            await sign_in(session, factory, username="skipper", password="")

        assert factory.asked == []

    async def test_a_refused_login_leaves_no_user_row(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        with pytest.raises(InvalidCredentialsError):
            await sign_in(session, factory, username="skipper", password="wrong")

        assert await session.scalar(select(func.count()).select_from(User)) == 0

    async def test_the_refusal_never_carries_the_password(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        """例外訊息會進 log，密碼不進 log（票 07 驗收）。"""
        refusal = await _refusal(session, factory, "skipper", "hunter2")

        assert "hunter2" not in str(refusal)

    async def test_an_unreachable_jellyfin_is_not_a_wrong_password(
        self, session: AsyncSession, jellyfin: FakeJellyfinClient
    ) -> None:
        """Jellyfin 掛掉時沒有人登得進來，但那不是使用者打錯了（brief §11 的取捨）。"""
        jellyfin.error = ServiceUnavailableError("connection refused")

        with pytest.raises(JellyfinUnavailableError):
            await sign_in(session, OneJellyfin(jellyfin), username="skipper", password="harbour")

    async def test_login_before_setup_says_so(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        """還沒有 Jellyfin 位址就沒有身分來源，那不是憑證問題。"""
        await write_settings(session, JellyfinSettings())
        await session.commit()

        with pytest.raises(JellyfinUnavailableError):
            await sign_in(session, factory, username="skipper", password="harbour")


@pytest.mark.usefixtures("configured")
class TestSessions:
    async def test_the_token_is_never_stored_in_the_clear(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        signed = await sign_in(session, factory, username="skipper", password="harbour")

        rows = (await session.scalars(select(UserSession))).all()
        assert len(rows) == 1
        assert signed.token not in rows[0].token_hash

    async def test_a_fresh_token_resolves_to_its_user(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        signed = await sign_in(session, factory, username="skipper", password="harbour")

        assert await read_session(session, signed.token) == signed.user

    async def test_an_unknown_token_resolves_to_nobody(self, session: AsyncSession) -> None:
        assert await read_session(session, "not-a-token") is None

    async def test_no_cookie_resolves_to_nobody(self, session: AsyncSession) -> None:
        assert await read_session(session, None) is None
        assert await read_session(session, "") is None

    async def test_a_fresh_session_lasts_the_whole_window(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        await sign_in(session, factory, username="skipper", password="harbour")

        row = (await session.scalars(select(UserSession))).one()
        assert row.expires_at - datetime.now(UTC) > SESSION_TTL - timedelta(minutes=1)

    async def test_an_expired_session_cannot_be_reused(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        signed = await sign_in(session, factory, username="skipper", password="harbour")
        await _expire(session, signed.token)

        assert await read_session(session, signed.token) is None

    async def test_an_expired_session_is_swept_away(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        """過期的列自己會消失，不必等背景工作（票 07 驗收）。"""
        signed = await sign_in(session, factory, username="skipper", password="harbour")
        await _expire(session, signed.token)

        await read_session(session, signed.token)

        assert await session.scalar(select(func.count()).select_from(UserSession)) == 0

    async def test_signing_out_invalidates_the_token(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        signed = await sign_in(session, factory, username="skipper", password="harbour")

        await sign_out(session, signed.token)

        assert await read_session(session, signed.token) is None

    async def test_signing_out_leaves_other_devices_alone(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        laptop = await sign_in(session, factory, username="skipper", password="harbour")
        phone = await sign_in(session, factory, username="skipper", password="harbour")

        await sign_out(session, laptop.token)

        assert await read_session(session, phone.token) is not None

    async def test_signing_out_twice_is_harmless(
        self, session: AsyncSession, factory: OneJellyfin
    ) -> None:
        signed = await sign_in(session, factory, username="skipper", password="harbour")

        await sign_out(session, signed.token)
        await sign_out(session, signed.token)
        await sign_out(session, None)


async def _refusal(
    session: AsyncSession, factory: OneJellyfin, username: str, password: str
) -> InvalidCredentialsError:
    with pytest.raises(InvalidCredentialsError) as raised:
        await sign_in(session, factory, username=username, password=password)
    return raised.value


async def _expire(session: AsyncSession, token: str) -> None:
    """把到期時間拉到過去，不必等三十天。"""
    row = await session.scalar(
        select(UserSession).where(UserSession.token_hash == token_digest(token))
    )
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()
