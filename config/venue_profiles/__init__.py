# -*- coding: utf-8 -*-
"""Venue profiles - 期刊/会议场景配置

支持的 Venue:
  期刊: TIP, TCSVT, TPAMI, IJCV, PR, Displays
  会议: CVPR, ICCV, ECCV, AAAI, NeurIPS
"""

from config.venue_profiles.base_profile import VenueProfile
from config.venue_profiles.journal_tip import IEEE_TIP_Profile
from config.venue_profiles.journal_csvt import IEEE_TCSVT_Profile
from config.venue_profiles.journal_tpami import IEEE_TPAMI_Profile
from config.venue_profiles.journal_ijcv import IJCV_Profile
from config.venue_profiles.journal_pr import PatternRecognition_Profile
from config.venue_profiles.journal_displays import Displays_Profile
from config.venue_profiles.conf_cvpr import CVPR_Profile
from config.venue_profiles.conf_iccv import ICCV_Profile
from config.venue_profiles.conf_eccv import ECCV_Profile
from config.venue_profiles.conf_aaai import AAAI_Profile
from config.venue_profiles.conf_neurips import NeurIPS_Profile

# Profile 注册表 — key 为 TARGET_VENUE 配置值
PROFILE_REGISTRY: dict[str, type[VenueProfile]] = {
    # 期刊
    "IEEE Trans": IEEE_TIP_Profile,
    "IEEE TIP": IEEE_TIP_Profile,
    "TIP": IEEE_TIP_Profile,
    "IEEE TCSVT": IEEE_TCSVT_Profile,
    "TCSVT": IEEE_TCSVT_Profile,
    "IEEE TPAMI": IEEE_TPAMI_Profile,
    "TPAMI": IEEE_TPAMI_Profile,
    "IJCV": IJCV_Profile,
    "PR": PatternRecognition_Profile,
    "Pattern Recognition": PatternRecognition_Profile,
    "Displays": Displays_Profile,
    # 会议
    "CVPR": CVPR_Profile,
    "ICCV": ICCV_Profile,
    "ECCV": ECCV_Profile,
    "AAAI": AAAI_Profile,
    "NeurIPS": NeurIPS_Profile,
}


def get_profile(venue_name: str) -> VenueProfile:
    """根据 TARGET_VENUE 获取对应的 venue profile"""
    profile_cls = PROFILE_REGISTRY.get(venue_name)
    if profile_cls is None:
        # 降级到 IEEE TIP 作为默认
        return IEEE_TIP_Profile()
    return profile_cls()
