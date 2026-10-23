"""
应用程序门面控制器 (ApplicationController)
采用面向对象门面模式 (Facade Pattern) 与依赖注入思想，
统一协调数据库仓储、领域引擎与各项业务服务，向 UI 层与测试层提供高内聚接口。
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from src.database.db_manager import DatabaseManager, get_default_db_path
from src.database.repositories import (
    ClientRepository,
    ConfigRepository,
    EatReportRepository,
    HistoryArchiveRepository,
    KeywordRepository,
    OrderRepository,
    RegionRepository,
    ReplaceRuleRepository,
)
from src.domain.attribute_engine import NumberAttributeEngine
from src.domain.models import (
    AppConfig,
    BookmakerRecord,
    ClientProfile,
    ClientSettlementItem,
    OrderRecord,
    ParsedBetItem,
    RegionConfig,
    ReplaceRule,
    RiskItem,
)
from .excel_migration_service import ExcelMigrationService
from .history_review_service import HistoryReviewService
from .risk_eat_service import RiskAndEatService
from .settlement_service import SettlementService
from .update_service import AutoUpdateService, ReleaseManifest, UpdateCheckResult
from .wechat_parser_service import WeChatParserService
from src.version import OFFICIAL_GITHUB_REPO


class ApplicationController:
    """系统核心门面控制器 (Facade)"""

    def __init__(self, db_path: str | Path | None = None, auto_seed: bool = True) -> None:
        resolved_path = db_path if db_path is not None else get_default_db_path()
        self.db_manager = DatabaseManager(resolved_path)
        self.config_repo = ConfigRepository(self.db_manager)
        self.region_repo = RegionRepository(self.db_manager)
        self.client_repo = ClientRepository(self.db_manager)
        self.order_repo = OrderRepository(self.db_manager)
        self.eat_repo = EatReportRepository(self.db_manager)
        self.keyword_repo = KeywordRepository(self.db_manager)
        self.replace_repo = ReplaceRuleRepository(self.db_manager)
        self.archive_repo = HistoryArchiveRepository(self.db_manager)

        # 加载配置与属性引擎
        self.app_config: AppConfig = self.config_repo.load_app_config()
        overrides = self.config_repo.load_attribute_overrides()
        self.attr_engine = NumberAttributeEngine(
            base_zodiac=self.app_config.base_zodiac,
            custom_overrides=overrides,
        )

        # 初始化业务服务
        self.risk_service = RiskAndEatService(
            attr_engine=self.attr_engine,
            region_repo=self.region_repo,
            client_repo=self.client_repo,
            eat_repo=self.eat_repo,
        )
        self.settlement_service = SettlementService(
            region_repo=self.region_repo,
            client_repo=self.client_repo,
            order_repo=self.order_repo,
            eat_repo=self.eat_repo,
        )
        self.migration_service = ExcelMigrationService(
            db=self.db_manager,
            config_repo=self.config_repo,
            region_repo=self.region_repo,
            client_repo=self.client_repo,
            order_repo=self.order_repo,
            eat_repo=self.eat_repo,
            keyword_repo=self.keyword_repo,
            attr_engine=self.attr_engine,
            risk_service=self.risk_service,
            settlement_service=self.settlement_service,
        )

        # 按日期历史回看与期数归档服务
        self.history_service = HistoryReviewService(
            order_repo=self.order_repo,
            archive_repo=self.archive_repo,
            client_repo=self.client_repo,
            region_repo=self.region_repo,
            settlement_service=self.settlement_service,
            risk_service=self.risk_service,
            attr_engine=self.attr_engine,
        )

        if auto_seed:
            self.migration_service.initialize_if_needed()

        self.parser_service = WeChatParserService(
            attr_engine=self.attr_engine,
            config=self.app_config,
            keywords_map=self.keyword_repo.get_all_categories_map(),
            replace_rules=self.replace_repo.list_rules(only_enabled=True),
        )
        self.update_service = AutoUpdateService()

        # 当前激活盘口与客户状态
        regions = self.region_repo.list_regions()
        if not regions:
            for idx, rname in enumerate(["新澳门", "香港", "旧澳门"], 1):
                self.region_repo.save_region(RegionConfig(name=rname, display_order=idx))
            regions = self.region_repo.list_regions()

        self.current_region: str = regions[0].name
        self._last_added_summary: str = ""

    @property
    def last_added_summary(self) -> str:
        return self._last_added_summary

    def reload_runtime_configs(self) -> None:
        """当用户修改配置、本命年生肖、关键字或替换规则后刷新内存引擎"""
        self.app_config = self.config_repo.load_app_config()
        overrides = self.config_repo.load_attribute_overrides()
        self.attr_engine.set_base_zodiac(self.app_config.base_zodiac)
        self.attr_engine.set_custom_overrides(overrides)
        self.parser_service.update_config(self.app_config)
        self.parser_service.update_keywords(self.keyword_repo.get_all_categories_map())
        self.parser_service.update_replace_rules(self.replace_repo.list_rules(only_enabled=True))

    def save_app_config(self, config: AppConfig) -> None:
        self.config_repo.save_app_config(config)
        self.reload_runtime_configs()

    def get_current_region_config(self) -> RegionConfig:
        reg = self.region_repo.get_region(self.current_region)
        if not reg:
            reg = RegionConfig(name=self.current_region)
            self.region_repo.save_region(reg)
        return reg

    def get_active_client(self, region: Optional[str] = None) -> ClientProfile:
        reg_name = region or self.current_region
        reg_cfg = self.region_repo.get_region(reg_name)
        clients = self.client_repo.list_clients(reg_name)
        if not clients:
            default_c = ClientProfile(id=None, region=reg_name, name="客户1", odds=47.0, rebate=0.0, sort_order=1)
            self.client_repo.save_client(default_c)
            clients = self.client_repo.list_clients(reg_name)

        if reg_cfg and reg_cfg.active_client_name:
            found = next((c for c in clients if c.name == reg_cfg.active_client_name), None)
            if found:
                return found

        first_client = clients[0]
        if reg_cfg:
            reg_cfg.active_client_name = first_client.name
            self.region_repo.save_region(reg_cfg)
        return first_client

    def set_active_client(self, client_name: str, region: Optional[str] = None) -> None:
        reg_name = region or self.current_region
        reg_cfg = self.region_repo.get_region(reg_name)
        if reg_cfg:
            reg_cfg.active_client_name = client_name
            self.region_repo.save_region(reg_cfg)

    def submit_bet_items(
        self,
        items: List[ParsedBetItem],
        raw_text: str = "",
        region: Optional[str] = None,
        client_name: Optional[str] = None,
    ) -> Optional[OrderRecord]:
        reg_name = region or self.current_region
        c_name = client_name or self.get_active_client(reg_name).name
        order = self.settlement_service.submit_parsed_order(reg_name, c_name, raw_text, items)
        if order:
            self._last_added_summary = order.parsed_content.replace("\n", " | ")
        return order

    def check_for_updates(self, timeout: float = 6.0) -> UpdateCheckResult:
        """根据官方锁定更新源检查远端版本更新"""
        cfg = self.app_config
        target_repo_or_url = cfg.update_repo_or_url or OFFICIAL_GITHUB_REPO
        # 若非本地测试清单文件，强制使用官方写死仓库地址防篡改
        is_local_test = (
            target_repo_or_url.endswith(".json")
            or Path(target_repo_or_url).exists()
            or target_repo_or_url.startswith("file://")
        )
        final_repo = target_repo_or_url if is_local_test else OFFICIAL_GITHUB_REPO
        final_mode = cfg.update_source_mode if is_local_test else "github_api"
        return self.update_service.check_for_updates(
            source_mode=final_mode,
            repo_or_url=final_repo,
            mirror_prefix=cfg.update_mirror_prefix,
            timeout=timeout,
        )

    def apply_hot_keywords_from_manifest(self, manifest: ReleaseManifest) -> int:
        """若远端版本清单附带 hot_keywords 增量词库，免重启直接热更新合并至本地 SQLite"""
        if not manifest.hot_keywords:
            return 0
        added = 0
        for cat, words in manifest.hot_keywords.items():
            if isinstance(words, list) and words:
                for w in words:
                    if w and str(w).strip():
                        self.keyword_repo.add_keyword(cat, str(w).strip())
                        added += 1
        if added > 0:
            self.reload_runtime_configs()
        return added
