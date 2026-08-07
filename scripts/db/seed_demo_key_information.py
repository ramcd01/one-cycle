from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal
from app.models import (
    Announcement,
    CollectionRun,
    Document,
    KeyInformation,
    ProcessingRun,
)


EXECUTION_ID = "demo-announcement-001"
ANNOUNCEMENT_KEY = "announcement_001"


APPLICATION_PERIOD = {
    "status": "available",
    "announcement_date": "2026-07-16",
    "contract_start": "2026-07-23 10:00",
    "end_condition": "별도 공지 시까지",
    "operating_hours": "10:00~16:00",
    "break_time": "12:00~13:00",
    "closed_days": "주말·공휴일",
    "location": "청주지북 B1블록 주택전시관",
    "note": (
        "잔여세대 소진 시 선착순 동호지정 계약이 종료되며 "
        "LH청약플러스 공지사항에 별도 공지"
    ),
    "source_section_ids": ["sec_0003"],
    "source_titles": ["계약 등 주요일정"],
}


ELIGIBILITY = {
    "status": "available",
    "summary": (
        "주택공급계약체결일 현재 국내에 거주하는 만 19세 이상 "
        "성년자와 법인이 신청할 수 있으며 외국인은 신청할 수 없음"
    ),
    "conditions": [
        "주택공급계약체결일 현재 국내 거주",
        "만 19세 이상 성년자 또는 법인",
        "외국인 신청 불가",
        "주택소유 여부 불문",
        "거주지역 불문",
        "입주자저축 가입 여부 불문",
        "과거 당첨 사실 여부 불문",
        "1세대 1주택 제한 없음",
    ],
    "minor_exception": (
        "민법상 미성년자는 직계존속의 사망·실종신고·행방불명 등으로 "
        "형제자매 또는 자녀를 부양해야 하는 세대주인 경우 신청 가능"
    ),
    "source_section_ids": ["sec_0018"],
    "source_titles": ["신청자격"],
}


SUPPLY_INFORMATION = {
    "status": "available",
    "block": "청주지북지구 B1블록",
    "housing_category": "공공분양주택",
    "total_public_sale_units": 757,
    "current_supply_units": 648,
    "supply_by_type": [
        {
            "type": "55A",
            "construction_units": 112,
            "contracted_units": 11,
            "current_supply_units": 101,
        },
        {
            "type": "55A-1",
            "construction_units": 20,
            "contracted_units": 1,
            "current_supply_units": 19,
        },
        {
            "type": "55B",
            "construction_units": 164,
            "contracted_units": 6,
            "current_supply_units": 158,
        },
        {
            "type": "59A",
            "construction_units": 279,
            "contracted_units": 82,
            "current_supply_units": 197,
        },
        {
            "type": "59A-1",
            "construction_units": 20,
            "contracted_units": 3,
            "current_supply_units": 17,
        },
        {
            "type": "59B",
            "construction_units": 131,
            "contracted_units": 3,
            "current_supply_units": 128,
        },
        {
            "type": "59C",
            "construction_units": 31,
            "contracted_units": 3,
            "current_supply_units": 28,
        },
    ],
    "price_unit": "천원",
    "contract_deposit": 10000,
    "price_by_type": [
        {
            "type": "55A",
            "minimum": 288580,
            "maximum": 307000,
        },
        {
            "type": "55A-1",
            "minimum": 288680,
            "maximum": 307110,
        },
        {
            "type": "55B",
            "minimum": 288620,
            "maximum": 307050,
        },
        {
            "type": "59A",
            "minimum": 309200,
            "maximum": 328940,
        },
        {
            "type": "59A-1",
            "minimum": 309260,
            "maximum": 329000,
        },
        {
            "type": "59B",
            "minimum": 309260,
            "maximum": 329000,
        },
        {
            "type": "59C",
            "minimum": 309300,
            "maximum": 329050,
        },
    ],
    "move_in_expected": "2028-03",
    "balcony_extension": "전 세대 발코니 확장형",
    "dynamic_remaining_units": True,
    "note": (
        "선착순 동호지정 계약 진행에 따라 실제 잔여세대는 "
        "신청 당일 달라질 수 있음"
    ),
    "source_section_ids": [
        "sec_0005",
        "sec_0006",
        "sec_0007",
        "sec_0008",
    ],
    "source_titles": [
        "공급규모",
        "공급대상",
        "공급금액(발코니 확장금액 별도) 및 납부 일정",
        "분양가격 납부조건 등 안내",
    ],
}


INCOME_ASSET_CRITERIA = {
    "status": "available",
    "required": False,
    "summary": "소득 및 자산요건을 적용하지 않음",
    "source_text": (
        "주택소유여부, 거주지역, 소득 및 자산요건, "
        "입주자저축 가입여부, 과거당첨사실여부를 불문"
    ),
    "source_section_ids": ["sec_0018"],
    "source_titles": ["신청자격"],
}


REQUIRED_DOCUMENTS = {
    "status": "available",
    "summary": (
        "계약서류는 입주자모집공고일(2026.07.16.) 이후 발급분을 "
        "원칙으로 하며 서류가 미비한 경우 계약할 수 없음"
    ),
    "personal_contract_examples": [
        "계약금 입금 확인서류",
        "신분증",
        "도장 또는 본인 서명",
        "주민등록표등본(상세발급)",
    ],
    "proxy_contract": {
        "additional_documents_required": True,
        "note": (
            "본인 외 계약은 대리계약으로 간주되며 "
            "본인 계약 서류와 함께 추가 서류 제출 필요"
        ),
    },
    "special_note": (
        "2026년 10월 이후 계약체결을 희망할 경우 "
        "계약체결일 기준 3개월 이내 발급분만 인정"
    ),
    "source_section_ids": ["sec_0022"],
    "source_titles": ["계약 시 구비서류"],
}


WINNER_ANNOUNCEMENT = {
    "status": "not_applicable",
    "applicable": False,
    "summary": (
        "이 공고는 선착순 동호지정 및 계약 방식이며 "
        "구조화된 공고문에서 별도의 당첨자 발표 일정은 확인되지 않음"
    ),
    "source_section_ids": [
        "sec_0003",
        "sec_0019",
        "sec_0020",
    ],
}


CONTACT_INFORMATION = {
    "status": "available",
    "showroom": {
        "name": "청주지북 B1블록 주택전시관",
        "address": "충청북도 청주시 상당구 용암동 3166번지",
        "operating_hours": "10:00~17:00",
        "phone": "043-292-2221",
    },
    "lh_call_center": {
        "phone": "1600-1004",
        "operating_hours": "평일 09:00~18:00",
    },
    "website": {
        "source_value": "wwww.cjb1.co.kr",
        "needs_review": True,
        "note": "공고문 구조화 결과의 표기값을 그대로 보존",
    },
    "source_section_ids": ["sec_0030"],
    "source_titles": ["주택전시관 및 공식홈페이지 안내"],
}


def main() -> None:
    with SessionLocal() as db:
        collection_run = db.scalar(
            select(CollectionRun).where(
                CollectionRun.execution_id == EXECUTION_ID
            )
        )

        if collection_run is None:
            raise RuntimeError(
                f"collection_run을 찾을 수 없습니다: {EXECUTION_ID}"
            )

        announcement = db.scalar(
            select(Announcement).where(
                Announcement.collection_run_id == collection_run.id,
                Announcement.source_announcement_id == ANNOUNCEMENT_KEY,
            )
        )

        if announcement is None:
            raise RuntimeError(
                f"announcement를 찾을 수 없습니다: {ANNOUNCEMENT_KEY}"
            )

        document = db.scalar(
            select(Document).where(
                Document.announcement_id == announcement.id
            )
        )

        if document is None:
            raise RuntimeError("document를 찾을 수 없습니다.")

        processing_run = db.scalar(
            select(ProcessingRun).where(
                ProcessingRun.document_id == document.id,
                ProcessingRun.is_active.is_(True),
            )
        )

        if processing_run is None:
            raise RuntimeError(
                "활성 processing_run을 찾을 수 없습니다."
            )

        key_information = db.scalar(
            select(KeyInformation).where(
                KeyInformation.announcement_id == announcement.id
            )
        )

        if key_information is None:
            key_information = KeyInformation(
                announcement_id=announcement.id,
                source_processing_run_id=processing_run.id,
            )
            db.add(key_information)

        key_information.source_processing_run_id = processing_run.id
        key_information.application_period = APPLICATION_PERIOD
        key_information.eligibility = ELIGIBILITY
        key_information.supply_information = SUPPLY_INFORMATION
        key_information.income_asset_criteria = INCOME_ASSET_CRITERIA
        key_information.required_documents = REQUIRED_DOCUMENTS
        key_information.winner_announcement = WINNER_ANNOUNCEMENT
        key_information.contact_information = CONTACT_INFORMATION
        key_information.extraction_status = "completed"
        key_information.is_verified = True

        db.commit()
        db.refresh(key_information)

        print()
        print("[핵심 정보 DB 저장 완료]")
        print(f"key_information_id     : {key_information.id}")
        print(f"announcement_id        : {announcement.id}")
        print(
            f"source_processing_run_id: "
            f"{key_information.source_processing_run_id}"
        )
        print(
            f"extraction_status      : "
            f"{key_information.extraction_status}"
        )
        print(
            f"is_verified            : "
            f"{key_information.is_verified}"
        )
        print(
            f"current_supply_units   : "
            f"{SUPPLY_INFORMATION['current_supply_units']}"
        )
        print(
            f"contract_start         : "
            f"{APPLICATION_PERIOD['contract_start']}"
        )


if __name__ == "__main__":
    main()