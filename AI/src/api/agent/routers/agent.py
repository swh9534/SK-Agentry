from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import get_db
from api.auth.auth import get_current_user
from api.user.models.user import User as UserModel
from api.user.models.user_report import UserReport
from api.user.schemas.user_report import UserCreateReport, UserReportResponse
from api.utils.enums import ReportTypeEnum
from api.agent.cruds import agent as report_crud

from analysis import analyze_company  # 분석 로직 및 벡터 DB 로더
from tools import load_vector_db  # 벡터 DB 로더
from sqlalchemy import select, desc
from api.user.models.user_report import UserReport
from api.agent.cruds.agent import create_recommended_agents  # 경로 맞게 import


router = APIRouter(prefix="/agent", tags=["Agent"])


@router.post("/analyze", response_model=UserReportResponse)
async def run_company_analysis(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    # ✅ 회사명은 로그인된 유저의 이름으로 자동 설정
    company_name = current_user.name

     # ✅ 가장 최신 리포트 created_date 가져오기

    result = await db.execute(
        select(UserReport)
        .where(UserReport.user_id == current_user.user_id)
        .order_by(desc(UserReport.created_date))
        .limit(1)
    )
    latest_report = result.scalars().first()
    latest_created_date = latest_report.created_date if latest_report else None

    # ✅ 유저 기반 분석 메타 정보 구성
    user_data = {
        "industry": current_user.industry.value if current_user.industry else "정보 없음",
        "scale": "스타트업" if current_user.scale < 50 else "중소기업" if current_user.scale < 300 else "대기업",
        "interests": current_user.interests.value if current_user.interests else "정보 없음",
        "budget_size": current_user.budget_size,
        "created_date": latest_created_date,
    }

    # 1. 벡터 DB 불러오기
    vector_db = load_vector_db()

    # 2. 분석 실행
    result = analyze_company(company_name, vector_db, user_data)

    # 3. 리포트 저장
    report_data = UserCreateReport(
        user_id=current_user.user_id,
        filename=result["summary_report_file"],
        format=ReportTypeEnum.MD
    )
    new_report = await report_crud.create_user_report(db, report_data)
    
    # 4. 추천된 에이전트 저장
    await create_recommended_agents(
        db=db,
        user_id=current_user.user_id,
        recommended_agents=result["recommended_agents"]
    )
    
    return new_report

@router.get("/getRecom", summary="자기 자신의 추천 에이전트 목록 조회")
async def get_my_recommended_agents(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    result = await report_crud.get_recommended_agents_by_user(db, current_user.user_id)
    if not result:
        raise HTTPException(status_code=404, detail="추천 에이전트가 없습니다.")
    return result

# ✅ 리포트 전체 조회 (현재 로그인 유저 기준)
@router.get("/getAllReport", response_model=list[UserReportResponse])
async def get_my_reports(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    reports = await report_crud.get_reports_by_user_id(db, current_user.user_id)
    return reports

# ✅ 전체 에이전트 목록 조회
@router.get("/all", response_model=list[dict], summary="모든 에이전트 목록 조회")
async def get_all_agents(
    db: AsyncSession = Depends(get_db)
):
    agents = await report_crud.get_all_agents(db)
    return [
        {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "display_name": agent.display_name,
            "description": agent.description,
            "category": agent.category,
            "llm_type": agent.llm_type,
            "language": agent.language,
            "features": agent.features,
            "is_active": agent.is_active,
            "image_url": agent.image_url,
        }
        for agent in agents
    ]

# ✅ 단일 리포트 조회
@router.get("/{report_id}", response_model=UserReportResponse)
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    report = await report_crud.get_report_by_id(db, report_id)
    if report is None or report.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")
    return report


@router.get("/report/{report_id}/content", response_model=str)
async def get_report_content(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    # 1. 리포트 조회
    report = await report_crud.get_report_by_id(db, report_id)
    if report is None or report.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")

    # 2. 파일 읽기 (CRUD 함수 활용)
    content = await report_crud.read_report_markdown_content(report)
    return content

@router.get("/detail/{agent_id}")
async def get_agent_detail(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
):
    agent_info = await report_crud.get_agent_by_id(db, agent_id)
    if not agent_info:
        raise HTTPException(status_code=404, detail="해당 에이전트를 찾을 수 없습니다.")
    return agent_info