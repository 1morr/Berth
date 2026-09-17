"""對真的 Jellyfin 說話（brief §20.7）。"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from berth.adapters.http import (
    HttpSession,
    NotFoundError,
    ProtocolMismatchError,
    json_body,
)
from berth.adapters.jellyfin import (
    JellyfinApiKey,
    JellyfinAuth,
    JellyfinFilters,
    JellyfinImage,
    JellyfinItem,
    JellyfinLibrary,
    JellyfinPage,
    JellyfinPolicy,
    JellyfinPublicInfo,
    JellyfinSource,
    JellyfinTask,
    JellyfinUserData,
    JellyfinView,
    NewLibrary,
    ParentImage,
    TypeOption,
)
from berth.domain import CollectionType, SortOrder

#: 插件下載與重啟都比一次探測慢得多，所以這個 client 的逾時比 `DEFAULT_TIMEOUT_SECONDS` 長。
JELLYFIN_TIMEOUT_SECONDS = 30.0

#: `Authorization` 的 `MediaBrowser` 形態。Jellyfin 用它辨識客戶端，登入時是必要的；
#: 10.9 起這是唯一不過時的寫法（`X-Emby-Authorization` 已 deprecated）。
_CLIENT = "Berth"
_DEVICE = "Berth"
_DEVICE_ID = "berth-server"

#: 代理出去的圖一律要 WebP。**不靠 `Accept` 協商**：發請求的是 Berth 不是瀏覽器，Jellyfin 看到的
#: `Accept` 說不出瀏覽器吃什麼；而 Berth 支援的瀏覽器都吃 WebP
#: （研究 §6：`format=Webp` 回 `image/webp`）。改它就要換 `ImageSize` 的值：格式不在 Berth 的
#: 網址裡，而那個網址被快取一年（`services/jellyfin_images.IMAGE_SIZES`）。
_IMAGE_FORMAT = "Webp"


class HttpJellyfinClient:
    """憑證是可變的：初始精靈期間匿名，`use_token` 之後帶 token 或 API key。

    兩者在標頭裡的形狀相同（`Token="…"`），所以登入 token 與 `Auth/Keys` 建出來的
    API key 走同一條路（2026-09-07 對 10.11.11 實測）。
    """

    def __init__(
        self,
        base_url: str,
        *,
        token: str = "",
        timeout: float = JELLYFIN_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url
        self._session = HttpSession(
            base_url, headers={"Authorization": _authorization(token)}, timeout=timeout
        )

    @property
    def base_url(self) -> str:
        return self._base_url

    def use_token(self, token: str) -> None:
        self._session.set_header("Authorization", _authorization(token))

    async def public_info(self) -> JellyfinPublicInfo:
        payload = await self._get("/System/Info/Public")
        if not isinstance(payload, dict) or "StartupWizardCompleted" not in payload:
            raise ProtocolMismatchError("/System/Info/Public: not a Jellyfin public info payload")
        return JellyfinPublicInfo(
            server_name=str(payload.get("ServerName", "")),
            version=str(payload.get("Version", "")),
            startup_wizard_completed=bool(payload["StartupWizardCompleted"]),
        )

    # --- 初始精靈 ---

    async def start_configuration(
        self, *, ui_culture: str, metadata_country_code: str, preferred_metadata_language: str
    ) -> None:
        await self._session.request(
            "POST",
            "/Startup/Configuration",
            json={
                "UICulture": ui_culture,
                "MetadataCountryCode": metadata_country_code,
                "PreferredMetadataLanguage": preferred_metadata_language,
            },
        )

    async def ensure_default_user(self) -> str:
        payload = await self._get("/Startup/User")
        return str(payload.get("Name", "")) if isinstance(payload, dict) else ""

    async def create_startup_user(self, name: str, password: str) -> bool:
        # 403 = 第一個使用者已經有密碼了（12.0 起）。**那是答案不是失敗**：`HttpSession` 會把它
        # 翻成 `AuthFailedError`，而精靈第 3 步的重試會因此永遠走不完（brief §20.9）。
        response = await self._session.request(
            "POST", "/Startup/User", json={"Name": name, "Password": password}, tolerate=(403,)
        )
        return response.status_code != 403

    async def set_remote_access(self, *, enabled: bool) -> None:
        await self._session.request(
            "POST", "/Startup/RemoteAccess", json={"EnableRemoteAccess": enabled}
        )

    async def complete_startup(self) -> None:
        await self._session.request("POST", "/Startup/Complete")

    # --- 憑證 ---

    async def authenticate(self, username: str, password: str) -> JellyfinAuth:
        response = await self._session.request(
            "POST", "/Users/AuthenticateByName", json={"Username": username, "Pw": password}
        )
        payload = json_body(response)
        if not isinstance(payload, dict) or "AccessToken" not in payload:
            raise ProtocolMismatchError("/Users/AuthenticateByName: no AccessToken in the response")
        user = payload.get("User") or {}
        policy = user.get("Policy") or {}
        return JellyfinAuth(
            token=str(payload["AccessToken"]),
            user_id=str(user.get("Id", "")),
            name=str(user.get("Name", "")),
            server_id=str(payload.get("ServerId", "")),
            is_administrator=bool(policy.get("IsAdministrator", False)),
        )

    async def api_keys(self) -> tuple[JellyfinApiKey, ...]:
        payload = await self._get("/Auth/Keys")
        items = payload.get("Items", []) if isinstance(payload, dict) else []
        return tuple(
            JellyfinApiKey(
                app_name=str(row.get("AppName", "")), access_token=str(row.get("AccessToken", ""))
            )
            for row in items
        )

    async def create_api_key(self, app: str) -> None:
        await self._session.request("POST", "/Auth/Keys", params={"app": app})

    # --- 媒體庫 ---

    async def libraries(self) -> tuple[JellyfinLibrary, ...]:
        payload = await self._get("/Library/VirtualFolders")
        if not isinstance(payload, list):
            raise ProtocolMismatchError("/Library/VirtualFolders: expected a list")
        return tuple(_library(row) for row in payload)

    async def available_type_options(
        self, collection_type: CollectionType
    ) -> tuple[TypeOption, ...]:
        payload = await self._get(
            "/Libraries/AvailableOptions", params={"libraryContentType": collection_type.value}
        )
        rows = payload.get("TypeOptions", []) if isinstance(payload, dict) else []
        return tuple(
            TypeOption(
                type=str(row.get("Type", "")),
                metadata_fetchers=_fetcher_names(row.get("MetadataFetchers")),
                image_fetchers=_fetcher_names(row.get("ImageFetchers")),
            )
            for row in rows
        )

    async def create_library(self, library: NewLibrary) -> None:
        await self._session.request(
            "POST",
            "/Library/VirtualFolders",
            params={
                "name": library.name,
                "collectionType": library.collection_type.value,
                "paths": library.path,
                "refreshLibrary": "false",
            },
            # body 是 `AddVirtualFolderDto`，`LibraryOptions` 要包一層。直接送 LibraryOptions
            # 一樣回 204，但整份設定會被靜默丟掉（brief §20.7）。
            json={"LibraryOptions": _library_options(library)},
        )

    async def add_library_path(self, library_name: str, path: str) -> None:
        await self._session.request(
            "POST",
            "/Library/VirtualFolders/Paths",
            params={"refreshLibrary": "false"},
            json={"Name": library_name, "Path": path, "PathInfo": {"Path": path}},
        )

    async def validate_path(self, path: str, *, is_file: bool = True) -> bool:
        """404 不是錯誤，是「看不到」。`ValidateWritable` 不送真：那會讓 Jellyfin 在
        媒體庫目錄裡自己建一個暫存檔，而 Berth 問的只是「你看得到我寫的這一個嗎」。
        """
        response = await self._session.request(
            "POST",
            "/Environment/ValidatePath",
            json={"Path": path, "IsFile": is_file, "ValidateWritable": False},
            tolerate=(404,),
        )
        return response.status_code != 404

    # --- 排程任務 ---

    async def scheduled_tasks(self) -> tuple[JellyfinTask, ...]:
        payload = await self._get("/ScheduledTasks")
        rows = payload if isinstance(payload, list) else []
        return tuple(
            JellyfinTask(
                id=str(row.get("Id", "")),
                key=str(row.get("Key", "")),
                name=str(row.get("Name", "")),
            )
            for row in rows
        )

    async def run_task(self, task_id: str) -> None:
        await self._session.request("POST", f"/ScheduledTasks/Running/{task_id}")

    # --- 入庫之後 ---

    async def notify_paths(self, paths: Sequence[str]) -> None:
        await self._session.request(
            "POST",
            "/Library/Media/Updated",
            json={"Updates": [{"Path": path, "UpdateType": "Created"} for path in paths]},
        )

    async def items(self, library_id: str, item_types: Sequence[str]) -> tuple[JellyfinItem, ...]:
        payload = await self._get(
            "/Items",
            params={
                "parentId": library_id,
                "recursive": "true",
                "includeItemTypes": ",".join(item_types),
                "fields": "Path,ProviderIds,MediaSources",
            },
        )
        return _items(payload)

    # --- 替某一位使用者瀏覽 ---

    async def user_views(self, user_id: str) -> tuple[JellyfinView, ...]:
        payload = await self._get("/UserViews", params={"userId": user_id})
        return tuple(
            JellyfinView(
                id=str(row.get("Id", "")),
                name=str(row.get("Name", "")),
                collection_type=str(row.get("CollectionType") or ""),
            )
            for row in _rows(payload, "/UserViews")
        )

    async def user_policy(self, user_id: str) -> JellyfinPolicy:
        payload = await self._get(f"/Users/{user_id}")
        policy = payload.get("Policy") if isinstance(payload, dict) else None
        if not isinstance(policy, dict):
            raise ProtocolMismatchError("/Users/{id}: no Policy in the response")
        return JellyfinPolicy(is_disabled=bool(policy.get("IsDisabled", False)))

    async def library_page(
        self,
        *,
        user_id: str,
        library_id: str,
        item_type: str,
        start: int,
        limit: int,
        sort_by: Sequence[str],
        sort_order: SortOrder,
        genres: Sequence[str],
        years: Sequence[int],
    ) -> JellyfinPage:
        params = {
            "userId": user_id,
            "parentId": library_id,
            "recursive": "true",
            "includeItemTypes": item_type,
            "sortBy": ",".join(sort_by),
            "sortOrder": sort_order.value,
            # jellyfin-web 的牆要的那幾格（研究 §7）；Primary 的 tag 是海報（票 04），
            # 觀看紀錄是票 05 讀的。
            "fields": "PrimaryImageAspectRatio,ProviderIds,Path",
            "imageTypeLimit": "1",
            "enableImageTypes": "Primary,Backdrop,Thumb",
            "startIndex": str(start),
            "limit": str(limit),
        }
        # 類型名可能含逗號，所以 Jellyfin 用 `|` 分；年份用逗號（研究 §3.1）。
        if genres:
            params["genres"] = "|".join(genres)
        if years:
            params["years"] = ",".join(str(year) for year in years)
        payload = await self._get("/Items", params=params)
        items = _items(payload)
        total = payload.get("TotalRecordCount")
        return JellyfinPage(items=items, total=total if isinstance(total, int) else len(items))

    async def library_filters(
        self, *, user_id: str, library_id: str, item_type: str
    ) -> JellyfinFilters:
        payload = await self._get(
            "/Items/Filters",
            params={"userId": user_id, "parentId": library_id, "includeItemTypes": item_type},
        )
        genres = payload.get("Genres") if isinstance(payload, dict) else None
        years = payload.get("Years") if isinstance(payload, dict) else None
        if not isinstance(genres, list) or not isinstance(years, list):
            raise ProtocolMismatchError("/Items/Filters: no Genres and Years in the response")
        return JellyfinFilters(
            genres=tuple(str(genre) for genre in genres),
            years=tuple(year for year in years if isinstance(year, int)),
        )

    async def library_index(
        self, *, user_id: str, library_id: str, item_type: str
    ) -> tuple[JellyfinItem, ...]:
        payload = await self._get(
            "/Items",
            params={
                "userId": user_id,
                "parentId": library_id,
                "recursive": "true",
                "includeItemTypes": item_type,
                "fields": "ProviderIds",
                # 圖只要 Primary 的 tag：篩選後的牆從這一份畫海報（M1.5 票 04）。它的 BlurHash 會
                # 跟著來（12.1.0 錄製），每部多一百多個位元組。
                "imageTypeLimit": "1",
                "enableImageTypes": "Primary",
                "enableUserData": "false",
                "enableTotalRecordCount": "false",
            },
        )
        return _items(payload)

    async def mark_played(self, *, user_id: str, item_id: str, played: bool) -> JellyfinUserData:
        path = f"/UserPlayedItems/{item_id}"
        method = "POST" if played else "DELETE"
        response = await self._session.request(
            method, path, params={"userId": user_id}, tolerate=(404,)
        )
        if response.status_code == 404:
            raise NotFoundError(f"{method} {path}: no such item for this user")
        payload = json_body(response)
        if not isinstance(payload, dict) or "Played" not in payload:
            raise ProtocolMismatchError(f"{method} {path}: not a user data payload")
        return _user_data(payload)

    async def resume(
        self, *, user_id: str, library_id: str | None, limit: int
    ) -> tuple[JellyfinItem, ...]:
        params = {**_watching(user_id, library_id, limit), "mediaTypes": "Video"}
        return _items(await self._get("/UserItems/Resume", params=params))

    async def next_up(
        self, *, user_id: str, library_id: str | None, limit: int, cutoff: datetime
    ) -> tuple[JellyfinItem, ...]:
        params = {
            **_watching(user_id, library_id, limit),
            # 伺服器預設是 `true`；jellyfin-web 送 `false`，看到一半的集才不會兩列都出現。
            "enableResumable": "false",
            # jellyfin-web 送 `Date.toISOString()`：UTC、毫秒、`Z`。
            "nextUpDateCutoff": cutoff.astimezone(UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
        }
        return _items(await self._get("/Shows/NextUp", params=params))

    # --- 圖片 ---

    async def image(
        self,
        item_id: str,
        image_type: str,
        *,
        tag: str,
        fill_width: int,
        fill_height: int,
        quality: int,
    ) -> JellyfinImage:
        path = f"/Items/{item_id}/Images/{image_type}"
        response = await self._session.request(
            "GET",
            path,
            params={
                "tag": tag,
                "fillWidth": str(fill_width),
                "fillHeight": str(fill_height),
                "quality": str(quality),
                "format": _IMAGE_FORMAT,
            },
            tolerate=(404,),
        )
        if response.status_code == 404:
            raise NotFoundError(f"GET {path}: no such image")
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            shown = content_type or "no content type"
            raise ProtocolMismatchError(f"GET {path}: {shown}, not an image")
        return JellyfinImage(content=response.content, content_type=content_type)

    async def aclose(self) -> None:
        await self._session.aclose()

    async def _get(self, path: str, *, params: dict[str, str] | None = None) -> Any:
        response = await self._session.request("GET", path, params=params)
        return json_body(response)


def _authorization(token: str) -> str:
    parts = [
        f'Client="{_CLIENT}"',
        f'Device="{_DEVICE}"',
        f'DeviceId="{_DEVICE_ID}"',
        'Version="1"',
    ]
    if token:
        parts.append(f'Token="{token}"')
    return "MediaBrowser " + ", ".join(parts)


def _rows(payload: Any, path: str) -> list[dict[str, Any]]:
    rows = payload.get("Items") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ProtocolMismatchError(f"{path}: no Items array in the response")
    return [row for row in rows if isinstance(row, dict)]


def _items(payload: Any) -> tuple[JellyfinItem, ...]:
    return tuple(_item(row) for row in _rows(payload, "/Items"))


def _item(row: dict[str, Any]) -> JellyfinItem:
    providers = row.get("ProviderIds") or {}
    tags = row.get("ImageTags") or {}
    return JellyfinItem(
        id=str(row.get("Id", "")),
        type=str(row.get("Type", "")),
        name=str(row.get("Name", "")),
        path=str(row.get("Path") or ""),
        tmdb_id=str(providers.get("Tmdb") or ""),
        sources=tuple(
            JellyfinSource(path=str(source["Path"]), name=str(source.get("Name") or ""))
            for source in row.get("MediaSources") or ()
            if isinstance(source, dict) and source.get("Path")
        ),
        series_id=str(row.get("SeriesId") or ""),
        year=year if isinstance(year := row.get("ProductionYear"), int) else None,
        primary_tag=str(tags.get("Primary") or ""),
        user_data=_user_data(data) if isinstance(data := row.get("UserData"), dict) else None,
        series_name=str(row.get("SeriesName") or ""),
        season=_number(row.get("ParentIndexNumber")),
        episode_start=_number(row.get("IndexNumber")),
        episode_end=_number(row.get("IndexNumberEnd")),
        thumb_tag=str(tags.get("Thumb") or ""),
        backdrop_tag=_first(row.get("BackdropImageTags")),
        series_thumb_tag=str(row.get("SeriesThumbImageTag") or ""),
        parent_thumb=_parent_image(row.get("ParentThumbItemId"), row.get("ParentThumbImageTag")),
        parent_backdrop=_parent_image(
            row.get("ParentBackdropItemId"), _first(row.get("ParentBackdropImageTags"))
        ),
    )


def _watching(user_id: str, library_id: str | None, limit: int) -> dict[str, str]:
    """繼續觀看與下一集共用的參數（jellyfin-web 首頁那兩列，研究 §7.2）。

    **`library_id` 是 `None` 時不帶 `parentId`**：Jellyfin 只在不帶的時候照這個人的媒體庫限縮。
    圖只開那兩列要的三種——不開的類型連上層借來的那幾格（`ParentThumb*`、`ParentBackdrop*`）都不會回
    （v12.0 `DtoService` 照 `GetImageLimit` 收錄）。
    """
    params = {
        "userId": user_id,
        "limit": str(limit),
        "imageTypeLimit": "1",
        "enableImageTypes": "Primary,Backdrop,Thumb",
        "enableTotalRecordCount": "false",
    }
    if library_id is not None:
        params["parentId"] = library_id
    return params


def _number(value: Any) -> int | None:
    # `bool` 是 `int` 的子類別，JSON 的 `true` 不是集號。
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _first(tags: Any) -> str:
    """`BackdropImageTags` 這種陣列的第一個；`imageTypeLimit=1` 時本來就只有一個。"""
    return str(tags[0]) if isinstance(tags, list) and tags else ""


def _parent_image(item_id: Any, tag: Any) -> ParentImage | None:
    return ParentImage(item_id=str(item_id), tag=str(tag)) if item_id and tag else None


def _user_data(row: dict[str, Any]) -> JellyfinUserData:
    """缺的格子不是錯：`PlayedPercentage` 與 `UnplayedItemCount` 本來就只在某些 item 上有
    （研究 §1.2）。"""
    percentage = row.get("PlayedPercentage")
    unplayed = row.get("UnplayedItemCount")
    return JellyfinUserData(
        played=bool(row.get("Played", False)),
        played_percentage=float(percentage) if isinstance(percentage, int | float) else 0.0,
        unplayed_item_count=unplayed if isinstance(unplayed, int) else None,
    )


def _library(row: dict[str, Any]) -> JellyfinLibrary:
    options = row.get("LibraryOptions") or {}
    return JellyfinLibrary(
        name=str(row.get("Name", "")),
        item_id=str(row.get("ItemId", "")),
        collection_type=str(row.get("CollectionType") or ""),
        locations=tuple(str(path) for path in row.get("Locations") or ()),
        type_options=tuple(
            TypeOption(
                type=str(option.get("Type", "")),
                metadata_fetchers=tuple(str(f) for f in option.get("MetadataFetchers") or ()),
                image_fetchers=tuple(str(f) for f in option.get("ImageFetchers") or ()),
            )
            for option in options.get("TypeOptions") or ()
        ),
    )


def _library_options(library: NewLibrary) -> dict[str, Any]:
    return {
        "Enabled": True,
        "PathInfos": [{"Path": library.path}],
        "PreferredMetadataLanguage": library.preferred_metadata_language,
        "MetadataCountryCode": library.metadata_country_code,
        # Berth 主動通知入庫（plan §8.2 的 `notify_paths`），不需要 Jellyfin 自己盯目錄。
        "EnableRealtimeMonitor": False,
        "SeasonZeroDisplayName": "Specials",
        "TypeOptions": [
            {
                "Type": option.type,
                "MetadataFetchers": list(option.metadata_fetchers),
                "MetadataFetcherOrder": list(option.metadata_fetchers),
                "ImageFetchers": list(option.image_fetchers),
                "ImageFetcherOrder": list(option.image_fetchers),
            }
            for option in library.type_options
        ],
    }


def _fetcher_names(rows: Any) -> tuple[str, ...]:
    """`AvailableOptions` 回的是 `{Name, Type}` 物件，媒體庫本身回的是字串陣列。"""
    if not isinstance(rows, list):
        return ()
    return tuple(str(row.get("Name", "")) for row in rows if isinstance(row, dict))
