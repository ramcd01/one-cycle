import { useState, useEffect } from "react";
import { CalendarDays, House, BadgeCheck, CircleDollarSign, FileText, FileStack, ChevronDown, ChevronUp } from "lucide-react";
import { UserLayout } from "../layout/UserLayout";
import { StatusPill } from "../common/StatusPill";
import { Icon } from "../common/Icons";
import { API_BASE_URL } from "../../App";

function InfoModal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 bg-slate-900/40 flex items-center justify-center z-[100] px-4" onClick={onClose}>
      <div className="bg-white w-full max-w-[560px] max-h-[85vh] overflow-auto rounded-2xl p-6 lg:p-8 relative shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <button className="absolute right-5 top-5 text-slate-400 hover:text-slate-600 text-2xl" onClick={onClose}>×</button>
        <h2 className="text-xl font-bold text-slate-900 mb-4">{title}</h2>
        {children}
      </div>
    </div>
  );
}

function SummaryCard({ icon, title, rows }: { icon: string; title: string; rows: string[][] }) {
  const iconNode = icon === "calendar" ? <CalendarDays size={20} /> : icon === "home" ? <House size={20} /> : icon === "eligibility" ? <BadgeCheck size={20} /> : icon === "price" ? <CircleDollarSign size={20} /> : <FileText size={20} />;
  return (
    <div className="border border-slate-200 rounded-lg p-4 mb-3">
      <h3 className="flex items-center gap-2 text-blue-600 text-[16px] lg:text-[17px] font-bold mb-3">
        <span>{iconNode}</span>{title}
      </h3>
      {rows.map(([k, v]) => (
        <div className="grid grid-cols-[80px_1fr] lg:grid-cols-[100px_1fr] gap-2 items-baseline text-[14px] lg:text-[15px] leading-relaxed mb-2 last:mb-0" key={k}>
          <b className="text-slate-500 font-semibold">{k}</b>
          <span className="text-slate-900 font-medium text-[15px] lg:text-[17px] break-keep">{v}</span>
        </div>
      ))}
    </div>
  );
}

type EvidenceItem = {
  chunkId: string | number;
  sectionTitle?: string | null;
  content: string;
  score?: number | null;
};

type ChatMessage = {
  role: "user" | "ai";
  text: string;
  time: string;
  evidence?: EvidenceItem[];
};

export function DetailScreen({ go, showToast, notice }: { go: (s: any) => void; showToast: (m: string) => void; notice?: any; }) {
  const [evidence, setEvidence] = useState<EvidenceItem[] | null>(null);
  const [input, setInput] = useState("");
  const [isSummaryOpen, setIsSummaryOpen] = useState(false);

  // 💡 초기값을 시연용 공고로 변경
  const [currentNotice, setCurrentNotice] = useState(notice || {
    id: 1, // 백엔드 DB와 일치해야 함
    title: "(계약금 1,000만원)청주지북B1블록 공공분양 잔여세대 추가 입주자모집(선착순 동호지정)",
    region: "충청북도",
    date: "2026.08.07",
    status: "공고중"
  });

  useEffect(() => {
    if (notice) setCurrentNotice(notice);
  }, [notice]);

  useEffect(() => {
    if (!notice?.id) return;
    fetch(`${API_BASE_URL}/announcements/${notice.id}`)
      .then((res) => res.ok ? res.json() : null)
      .then((data) => { if (data) setCurrentNotice(data); })
      .catch(() => {});
  }, [notice]);

  const scheduleData = [["공고일", currentNotice.date], ["접수기간", "추후 안내 (상세 참조)"]];
  const supplyData = [["공급 위치", currentNotice.region || "해당 공고문 참조"], ["공급 세대수", "해당 공고문 참조"]];
  const eligibilityData = [["신청 자격", "공고문 세부 요건 참조"], ["소득 기준", "공고문 세부 요건 참조"]];
  const docsData = ["주민등록등본", "가족관계증명서", "소득금액증명원 등"];

  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const send = async () => {
    if (!input.trim()) return showToast("질문을 입력해 주세요.");
    const now = new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false });
    const userMsg = input.trim();

    setMessages((m) => [...m, { role: "user", text: userMsg, time: now }]);
    setInput("");
    showToast("AI가 답변을 생성하고 있습니다.");

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ announcementId: currentNotice.id, question: userMsg })
      });
      if (!response.ok) throw new Error();
      const data = await response.json();

      setMessages((m) => [...m, { role: "ai", text: data.answer, time: now, evidence: Array.isArray(data.evidence) ? data.evidence : [] }]);
    } catch {
      // 💡 가짜로 지연시간 주던 로직 삭제 -> 실제 서버 에러 시 에러메시지 출력
      setMessages((m) => [...m, { role: "ai", text: "서버 통신에 실패했습니다. 백엔드 서버가 연결되어 있는지 확인해주세요.", time: now }]);
    }
  };

  return (
    <UserLayout screen="detail" go={go} showToast={showToast}>
      <button className="flex items-center gap-1.5 text-[15px] lg:text-[16px] font-bold text-slate-600 hover:text-slate-900 mb-4 lg:mb-6 transition-colors" onClick={() => go("list")}>
        <Icon name="back" size={18} /> 목록으로 돌아가기
      </button>

      <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-[26px] lg:text-[30px] font-extrabold text-slate-900 leading-tight tracking-tight mb-3 lg:mb-4">공고 상세 및 AI 질의응답</h1>
          <div className="flex flex-col lg:flex-row lg:items-center gap-3">
            <div className="flex-shrink-0"><StatusPill>{currentNotice.status || "공고중"}</StatusPill></div>
            <strong className="text-[17px] lg:text-[20px] text-slate-900 leading-snug">{currentNotice.title}</strong>
          </div>
          <div className="text-[13px] lg:text-[15px] text-slate-500 mt-3">
            <span className="mr-2">공고일</span> <span className="text-slate-800 font-medium mr-5">{currentNotice.date}</span>
            <span className="mr-2">공고 상태</span> <span className="text-slate-800 font-medium mr-5">{currentNotice.status || "공고중"}</span>
            {currentNotice.region && <><span className="mr-2">지역</span><span className="text-slate-800 font-medium">{currentNotice.region}</span></>}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[340px_1fr] items-start gap-4 lg:gap-5">

        <div className="bg-white border border-slate-200 rounded-xl p-4 lg:p-5 shadow-sm">
          <div
            className="flex items-center justify-between cursor-pointer xl:cursor-default"
            onClick={() => setIsSummaryOpen(!isSummaryOpen)}
          >
            <h2 className="text-[17px] lg:text-[19px] font-bold text-slate-900">핵심 정보 요약</h2>
            <button className="xl:hidden text-slate-500 hover:text-slate-800 p-1">
              {isSummaryOpen ? <ChevronUp size={22} /> : <ChevronDown size={22} />}
            </button>
          </div>

          <div className={`${isSummaryOpen ? "block mt-4" : "hidden"} xl:block xl:mt-4`}>
            <SummaryCard icon="calendar" title="신청 일정" rows={scheduleData} />
            <SummaryCard icon="home" title="공급 정보" rows={supplyData} />
            <SummaryCard icon="eligibility" title="신청 자격" rows={eligibilityData} />

            <div className="relative border border-slate-200 rounded-lg p-4 mb-2">
              <h3 className="flex items-center gap-2 text-blue-600 text-[16px] lg:text-[17px] font-bold mb-3"><FileStack size={20} /> 제출 서류</h3>
              <ul className="text-[15px] lg:text-[17px] font-medium text-slate-800 leading-relaxed pl-5 list-disc mb-10">
                {docsData.map(d => <li key={d}>{d}</li>)}
              </ul>
              <button className="absolute right-4 bottom-4 h-9 px-3 border border-slate-300 rounded-md text-[13px] font-semibold text-slate-600 hover:bg-slate-50">
                상세 서류 보기
              </button>
            </div>
            <p className="text-[12px] text-slate-400 mt-3 break-keep">※ 핵심 정보는 공고문을 AI가 분석하여 추출한 내용으로, 실제 공고문을 원본으로 확인하세요.</p>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 lg:p-5 shadow-sm flex flex-col h-[600px] lg:h-[700px]">
          <h2 className="text-[17px] lg:text-[19px] font-bold text-slate-900 mb-1">AI에게 무엇이든 물어보세요</h2>
          <p className="text-[13px] lg:text-[14px] text-slate-500 mb-4">공고에 대해 궁금한 내용을 질문하면 AI가 답변해 드립니다.</p>

          <div className="flex-1 overflow-auto px-2 py-4 bg-slate-50/50 rounded-lg border border-slate-100">
            {messages.map((m, i) => m.role === "user" ? (
              <div key={i} className="flex flex-col items-end mb-5">
                <div className="max-w-[80%] lg:max-w-[65%] bg-blue-600 text-white text-[14px] lg:text-[15px] leading-relaxed px-4 py-3 rounded-2xl rounded-br-sm shadow-sm whitespace-pre-wrap break-keep">{m.text}</div>
                <small className="text-[11px] text-slate-400 mt-1.5">{m.time}</small>
              </div>
            ) : (
              <div key={i} className="flex items-start gap-2.5 mb-5">
                <div className="w-8 h-8 rounded-full border-2 border-blue-500 text-blue-600 flex items-center justify-center text-[12px] font-black flex-shrink-0 bg-white shadow-sm">AI</div>
                <div className="flex flex-col items-start max-w-[80%] lg:max-w-[70%]">
                  <div className="bg-white border border-slate-200 text-slate-800 text-[14px] lg:text-[15px] leading-relaxed px-4 py-3 rounded-2xl rounded-tl-sm shadow-sm whitespace-pre-wrap break-keep">
                    {m.text}
                    {m.evidence && m.evidence.length > 0 && (
                      <button onClick={() => setEvidence(m.evidence || [])} className="block mt-3 bg-blue-50 text-blue-600 text-[13px] font-bold px-3 py-1.5 rounded-md hover:bg-blue-100 transition-colors">
                        근거 문단 보기
                      </button>
                    )}
                  </div>
                  <small className="text-[11px] text-slate-400 mt-1.5">{m.time}</small>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4">
            <div className="flex h-12 lg:h-14 border border-slate-300 rounded-lg overflow-hidden focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100 transition-all shadow-sm">
              <input
                className="flex-1 border-0 px-4 outline-none text-[14px] lg:text-[15px]"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && send()}
                placeholder="궁금한 내용을 입력하세요."
              />
              <button onClick={send} className="w-[50px] lg:w-[60px] bg-white text-blue-600 hover:bg-blue-50 flex items-center justify-center transition-colors">
                <Icon name="send" size={20} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {evidence && (
        <InfoModal title="답변 근거" onClose={() => setEvidence(null)}>
          <p className="text-slate-500 text-sm mb-4">AI 답변에 실제 사용된 원문 문단입니다.</p>
          <div className="space-y-4">
            {evidence.map((item, index) => (
              <div key={`${item.chunkId}-${index}`} className="border border-slate-200 rounded-lg p-4">
                <div className="text-[13px] text-slate-500 mb-2">
                  <b className="text-slate-700 mr-2">근거 {index + 1}</b>
                  {item.sectionTitle || "문서 위치 미상"}
                </div>
                <div className="text-[14px] text-slate-800 leading-relaxed whitespace-pre-wrap break-keep">
                  {item.content}
                </div>
                {typeof item.score === "number" && (
                  <div className="text-[11px] text-slate-400 mt-2">score: {item.score.toFixed(4)}</div>
                )}
              </div>
            ))}
          </div>
          <div className="flex justify-end mt-6">
            <button onClick={() => setEvidence(null)} className="bg-blue-600 text-white font-bold px-5 py-2.5 rounded-lg hover:bg-blue-700 transition-colors">닫기</button>
          </div>
        </InfoModal>
      )}
    </UserLayout>
  );
}