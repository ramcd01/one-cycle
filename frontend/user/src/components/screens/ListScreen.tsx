// ListScreen.tsx 전체 복사/붙여넣기
import { useState, useMemo, useEffect } from "react";
import { ChevronRight } from "lucide-react";
import { UserLayout } from "../layout/UserLayout";
import { DropdownSelect } from "../common/DropdownSelect";
import { Pagination } from "../common/Pagination";
import { StatusPill } from "../common/StatusPill";
import { Icon } from "../common/Icons";
import { API_BASE_URL } from "../../App";

// 💡 시연용 공고 1개만 띄우도록 수정
const defaultAnnouncements = [
  {
    id: 1, // 백엔드 DB에 저장된 실제 ID 값으로 반드시 변경해주세요!
    title: "(계약금 1,000만원)청주지북B1블록 공공분양 잔여세대 추가 입주자모집(선착순 동호지정)",
    region: "충청북도",
    date: "2026.08.07",
    status: "공고중"
  }
];

type Screen = "list" | "detail" | "guide" | "glossary" | "admin-notices" | "admin-docs" | "admin-errors";

export function ListScreen({
  go,
  showToast,
}: {
  go: (s: Screen, notice?: any) => void;
  showToast: (m: string) => void;
}) {
  const [announcements, setAnnouncements] = useState(defaultAnnouncements);
  const [query, setQuery] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [region, setRegion] = useState("지역 전체");
  const [status, setStatus] = useState("공고 상태 전체");
  const [sort, setSort] = useState("최신순");
  const [page, setPage] = useState(1);
  const pageSize = 6;

  useEffect(() => {
    fetch(`${API_BASE_URL}/announcements`)
      .then((res) => res.ok ? res.json() : null)
      .then((data) => {
          if (!data || !Array.isArray(data.items)) return;

          const items = data.items.map((item: any) => ({
            id: item.id,
            title: item.title,
            region: item.region ?? "-",
            date: item.announcementDate ?? "",
            status: item.publicationStatus ?? "",
          }));

          setAnnouncements(items);
        })
      .catch(() => {});
  }, []);

  const filtered = useMemo(() => announcements.filter(
    (a) =>
      (!searchQuery || a.title.toLowerCase().includes(searchQuery.toLowerCase())) &&
      (region === "지역 전체" || a.region === region) &&
      (status === "공고 상태 전체" || a.status === status)
  ).sort((a, b) => sort === "최신순" ? b.date.localeCompare(a.date) : a.date.localeCompare(b.date)), [announcements, searchQuery, region, status, sort]);

  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const visible = filtered.slice((page - 1) * pageSize, page * pageSize);

  useEffect(() => { if (page > pages) setPage(pages); }, [pages, page]);

  const search = () => {
    setSearchQuery(query.trim());
    setPage(1);
    showToast(query.trim() ? `'${query.trim()}' 검색 결과를 반영했습니다.` : "전체 공고를 표시합니다.");
  };

  const goToDetail = (noticeItem: any) => {
    go("detail", noticeItem);
  };

  return (
    <UserLayout screen="list" go={go} showToast={showToast}>
      <section className="mb-6 lg:mb-8">
        <h1 className="text-[26px] lg:text-[30px] font-extrabold text-slate-900 tracking-tight leading-tight">분양주택 공고 목록</h1>
        <p className="text-sm lg:text-base text-slate-500 mt-2">LH 청약플러스의 분양주택 공고를 제공합니다.</p>
      </section>

      <div className="bg-white border border-slate-200 rounded-xl p-5 lg:p-6 shadow-sm mb-6 lg:mb-8">
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(400px,1fr)_140px_160px_120px] gap-3 lg:gap-4 items-center">
          <label className="flex border border-slate-300 rounded-lg overflow-hidden h-11 lg:h-12 focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100 transition-all">
            <input
              className="flex-1 border-0 px-4 outline-none text-sm lg:text-base w-full"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && search()}
              placeholder="공고명 검색"
            />
            <button onClick={search} className="w-[60px] lg:w-[72px] bg-blue-600 text-white font-bold hover:bg-blue-700 transition-colors">검색</button>
          </label>
          <DropdownSelect label="지역 필터" values={["지역 전체", "울산광역시", "충청북도", "충청남도", "경기도", "경상남도"]} value={region} onChange={(v) => { setRegion(v); setPage(1); }} />
          <DropdownSelect label="공고 상태 필터" values={["공고 상태 전체", "공고중", "정정공고중", "마감"]} value={status} onChange={(v) => { setStatus(v); setPage(1); }} />
          <DropdownSelect label="정렬" className="lg:ml-auto w-full" values={["최신순", "오래된순"]} value={sort} onChange={(v) => { setSort(v); setPage(1); }} />
        </div>
        <p className="flex items-center gap-2 text-xs lg:text-[13px] text-slate-500 mt-5">
          <Icon name="info" size={14} /> 총 {filtered.length}건의 공고가 있습니다.
        </p>
      </div>

      <div className="hidden lg:block bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
        <div className="grid grid-cols-[80px_minmax(500px,1fr)_140px_130px_130px_40px] items-center h-[52px] bg-slate-50 border-b border-slate-200 text-[15px] font-bold text-slate-700 px-2">
          <div className="px-4">번호</div>
          <div className="px-4">공고명</div>
          <div className="px-4">지역</div>
          <div className="px-4">공고일</div>
          <div className="px-4">공고 상태</div>
          <div></div>
        </div>
        {visible.map((a) => (
          <button
            key={a.id}
            onClick={() => goToDetail(a)}
            className="w-full grid grid-cols-[80px_minmax(500px,1fr)_140px_130px_130px_40px] items-center min-h-[68px] border-b border-slate-100 bg-white hover:bg-blue-50/50 text-left text-[14px] text-slate-700 transition-colors px-2"
          >
            <div className="px-4 font-bold text-[16px] text-slate-600">{a.id}</div>
            <div className="px-4 font-semibold text-[16px] text-slate-900 leading-relaxed pr-8">{a.title}</div>
            <div className="px-4 text-[14px]">{a.region}</div>
            <div className="px-4 text-[14px]">{a.date}</div>
            <div className="px-4"><StatusPill>{a.status}</StatusPill></div>
            <div className="text-slate-400 text-xl">›</div>
          </button>
        ))}
        {visible.length === 0 && <div className="py-12 text-center text-slate-500">조건에 맞는 공고가 없습니다.</div>}
        <Pagination pages={pages} page={page} onChange={(p) => { setPage(p); window.scrollTo({ top: 0, behavior: "smooth" }); showToast(`${p}페이지로 이동했습니다.`); }} />
      </div>

      <div className="flex flex-col gap-3 lg:hidden">
        {visible.map((a) => (
          <button
            key={`mobile-${a.id}`}
            onClick={() => goToDetail(a)}
            className="w-full bg-white border border-slate-200 rounded-xl p-4 text-left shadow-sm flex items-start gap-3 active:bg-slate-50 transition-colors"
          >
            <span className="text-blue-600 font-black text-[16px] pt-0.5">{a.id}</span>
            <div className="flex-1 min-w-0">
              <strong className="block text-[16px] font-extrabold text-slate-900 leading-snug mb-2.5 break-keep">
                {a.title}
              </strong>
              <div className="flex flex-wrap items-center gap-2 text-[12px] text-slate-500">
                <span>{a.region}</span>
                <span className="w-px h-3 bg-slate-300"></span>
                <span>{a.date}</span>
                <span className="w-px h-3 bg-slate-300"></span>
                <StatusPill>{a.status}</StatusPill>
              </div>
            </div>
            <ChevronRight className="text-slate-400 self-center flex-shrink-0" size={24} />
          </button>
        ))}
        {visible.length === 0 && <div className="py-10 text-center text-sm text-slate-500">조건에 맞는 공고가 없습니다.</div>}
        <Pagination pages={pages} page={page} onChange={(p) => { setPage(p); window.scrollTo({ top: 0, behavior: "smooth" }); showToast(`${p}페이지로 이동했습니다.`); }} />
      </div>
    </UserLayout>
  );
}