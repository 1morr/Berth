"""對真的 Jellyfin 說話（brief §20.7）。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from berth.adapters.http import (
    HttpSession,
    ProtocolMismatchError,
    json_body,
)
from berth.adapters.jellyfin import (
    JellyfinApiKey,
    JellyfinAuth,
    JellyfinItem,
    JellyfinLibrary,
    JellyfinPlugin,
    JellyfinPublicInfo,
    JellyfinRepository,
    JellyfinTask,
    NewLibrary,
    TypeOption,
)
from berth.domain import CollectionType

#: 插件下載與重啟都比一次探測慢得多，所以這個 client 的逾時比 `DEFAULT_TIMEOUT_SECONDS` 長。
JELLYFIN_TIMEOUT_SECONDS = 30.0

#: `Authorization` 的 `MediaBrowser` 形態。Jellyfin 用它辨識客戶端，登入時是必要的；
#: 10.9 起這是唯一不過時的寫法（`X-Emby-Authorization` 已 deprecated）。
_CLIENT = "Berth"
_DEVICE = "Berth"
_DEVICE_ID = "berth-server"


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

    async def create_startup_user(self, name: str, password: str) -> None:
        await self._session.request(
            "POST", "/Startup/User", json={"Name": name, "Password": password}
        )

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

    # --- 插件與排程任務 ---

    async def repositories(self) -> tuple[JellyfinRepository, ...]:
        payload = await self._get("/Repositories")
        rows = payload if isinstance(payload, list) else []
        return tuple(
            JellyfinRepository(
                name=str(row.get("Name", "")),
                url=str(row.get("Url", "")),
                enabled=bool(row.get("Enabled", True)),
            )
            for row in rows
        )

    async def set_repositories(self, repositories: tuple[JellyfinRepository, ...]) -> None:
        await self._session.request(
            "POST",
            "/Repositories",
            json=[
                {"Name": repo.name, "Url": repo.url, "Enabled": repo.enabled}
                for repo in repositories
            ],
        )

    async def package_versions(self, name: str) -> tuple[str, ...]:
        payload = await self._get("/Packages")
        rows = payload if isinstance(payload, list) else []
        for row in rows:
            # `/Packages` 是 manifest 的原文轉發，鍵是 camelCase 而不是 Jellyfin 自己的
            # PascalCase（實測 10.11.11）。
            if str(row.get("name", "")) == name:
                return tuple(str(v.get("version", "")) for v in row.get("versions", []))
        return ()

    async def install_package(self, name: str, *, assembly_guid: str) -> None:
        await self._session.request(
            "POST", f"/Packages/Installed/{name}", params={"assemblyGuid": assembly_guid}
        )

    async def plugins(self) -> tuple[JellyfinPlugin, ...]:
        payload = await self._get("/Plugins")
        rows = payload if isinstance(payload, list) else []
        return tuple(
            JellyfinPlugin(
                id=str(row.get("Id", "")).replace("-", "").lower(),
                name=str(row.get("Name", "")),
                version=str(row.get("Version", "")),
            )
            for row in rows
        )

    async def restart(self) -> None:
        await self._session.request("POST", "/System/Restart")

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
        rows = payload.get("Items") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise ProtocolMismatchError("/Items: no Items array in the response")
        return tuple(_item(row) for row in rows if isinstance(row, dict))

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


def _item(row: dict[str, Any]) -> JellyfinItem:
    providers = row.get("ProviderIds") or {}
    return JellyfinItem(
        id=str(row.get("Id", "")),
        type=str(row.get("Type", "")),
        name=str(row.get("Name", "")),
        path=str(row.get("Path") or ""),
        tmdb_id=str(providers.get("Tmdb") or ""),
        source_paths=tuple(
            str(source["Path"])
            for source in row.get("MediaSources") or ()
            if isinstance(source, dict) and source.get("Path")
        ),
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
