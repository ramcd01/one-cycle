import { useEffect, useMemo, useState } from 'react'
import {
  Search, ChevronDown, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight,
  ArrowLeft, ExternalLink, Send, Info, List, BookOpen, FileText, UserRound,
  TriangleAlert, LogOut, ClipboardList, CalendarDays, House, CircleDollarSign,
  BadgeCheck, FileStack, Upload, Download, MoreVertical, Check, X, Settings,
  RefreshCw, Eye, Bot, MessageCircle, FileCheck2, Database, CircleHelp
} from 'lucide-react'

type Screen = 'list' | 'detail' | 'guide' | 'glossary' | 'admin-notices' | 'admin-docs' | 'admin-errors'

type Announcement = {
  id: number
  title: string
  region: string
  date: string
  status: '공고중' | '정정공고중' | '마감'
}

type Toast = { message: string; id: number } | null

const announcements: Announcement[] = [
  { id: 1, title: '울산다운2 A-9 신혼희망타운 선착순 동호지정 공고(5년무이자 할부 및 발코니비용 무상)', region: '울산광역시', date: '2026.05.21', status: '공고중' },
  { id: 2, title: '아산배방LH4단지 오피스텔(공공분양) 잔여세대 선착순 동호지정 공고', region: '충청남도', date: '2026.05.21', status: '정정공고중' },
  { id: 3, title: '[정정공고]아산배방LH4단지 오피스텔(공공분양) 잔여세대 선착순 동호지정 공고', region: '충청남도', date: '2026.05.22', status: '공고중' },
  { id: 4, title: 'e편한세상 분당 퍼스트힐리지(성남낙생 A-1BL) 신혼희망타운(공공분양) 입주자 모집공고', region: '경기도', date: '2026.05.29', status: '정정공고중' },
  { id: 5, title: '양산시 매입임대 잔여주택 일반매각 선착순 동호지정 공고(상시, 유주택자 계약가능)', region: '경상남도', date: '2026.05.29', status: '공고중' },
  { id: 6, title: '창원시 매입임대 잔여주택 일반매각 선착순 동호지정 공고(상시, 유주택자 계약가능)', region: '경상남도', date: '2026.06.10', status: '공고중' },
  { id: 7, title: '역곡지구 하우스토리(부천역곡 A-2블록) 신혼희망타운(공공분양) 입주자모집공고', region: '경기도', date: '2026.06.26', status: '정정공고중' },
  { id: 8, title: '[정정공고]역곡지구 하우스토리(부천역곡 A-2블록) 신혼희망타운(공공분양) 입주자모집공고', region: '경기도', date: '2026.06.26', status: '정정공고중' },
]

const glossary = [
  ['무주택 세대구성원', '세대 구성원 모두가 주택을 소유하고 있지 않은 상태를 의미합니다.'],
  ['도시근로자 월평균소득', '통계청이 발표하는 도시 근로자 가구당 월평균 소득을 기준으로, 신청 자격의 소득 기준으로 활용됩니다.'],
  ['특별공급', '국가유공자, 신혼부부, 다자녀가구, 노부모부양 등 일정 요건을 충족하는 대상자에게 주택을 우선 공급하는 제도입니다.'],
  ['신혼희망타운', '신혼부부 및 예비신혼부부, 한부모가족 등을 위한 전용 공공주택 단지입니다.'],
  ['공공분양', '국가, 지자체 또는 공공기관이 건설한 주택을 국민에게 분양하는 제도입니다.'],
  ['선착순 동호지정', '잔여 세대에 대해 정해진 순서대로 원하는 동·호수를 선택하여 계약하는 방식입니다.'],
]

const adminNoticeRows = [
  ['24','울산다운2 A-9 신혼희망타운\n선착순 동호지정 공고(5년무이자 할부 및 발코니비용 무상)','울산광역시','2026.05.21','2026.05.21 ~ 2027.01.31','수집완료','공고중','완료'],
  ['23','아산배방 LH4단지 오피스텔(공공분양) 잔여세대\n선착순 동호지정 공고','충청남도','2026.05.21','2026.05.21 ~ 2026.05.31','수집완료','공고중','완료'],
  ['22','[정리]그날의아산배방 LH4단지 오피스텔(공공분양)\n잔여세대 선착순 동호지정 공고','충청남도','2026.05.22','2026.05.22 ~ 2026.05.31','수집완료','공고중','완료'],
  ['21','e편한세상 당정 퍼스트힐(지산1~4BL)\n신혼희망타운(공공분양) 입주자 모집공고','경기도','2026.05.29','2026.05.29 ~ 2026.06.08','수집중','공고중','처리중'],
  ['20','안산신 매입임대 잔여주택 일반매각 선착순\n동호지정 공고(상시, 유주택자 계약가능)','경상남도','2026.05.29','2026.05.29 ~ 2026.06.30','수집실패','공고중','실패'],
  ['19','남양주별내 A-1블록 신혼희망타운(공공분양)','경기도','2026.05.30','-','미수집','공고예정','-'],
  ['18','의정부우정 A-2블록 신혼희망타운(공공분양)','경기도','2026.06.01','-','미수집','공고예정','-'],
]

const errorRows = [
  ['26','2026.06.01 11:30','문서 가공','문서 처리','부산에코델타시티 11블록...','이미지 데이터 손실','미해결','-'],
  ['25','2026.05.31 14:22','분석 처리','AI 분석','인천계양 A-2블록 신혼희망타운...','텍스트 추출 실패','해결 중','재처리 예정'],
  ['24','2026.05.30 09:15','수집','공고 수집','의정부우정 A-2블록...','페이지 로드 타임아웃','해결 완료','수집 재시도 후 성공'],
  ['23','2026.05.29 16:40','문서 저장','문서 처리','안산신매입임대 잔여주택...','파일 저장 실패 (권한 오류)','미해결','권한 설정 필요'],
  ['22','2026.05.28 10:05','분석 처리','AI 분석','남양주별내 A-1블록...','분석 중 서버 오류','해결 중','서버 재시작 후 재처리'],
  ['21','2026.05.27 13:18','수집','공고 수집','화성동탄 A-110블록...','공고 상세 페이지 파싱 실패','해결 완료','선택자 수정 후 수집 성공'],
  ['20','2026.05.26 08:47','문서 가공','문서 처리','아산배방 LH4단지 오피스텔...','PDF 손상 파일','미해결','원본 파일 확인 필요'],
  ['19','2026.05.25 22:10','분석 처리','AI 분석','광주남구 도시첨단 D1블록...','임베딩 생성 실패','해결 중','파라미터 조정 후 재시도'],
]

const documentRows = [
  ['DOC-001','울산다운2 A-9 공고문.hwpx','HWPX','파싱 완료','구조화 완료','2026.07.17 13:45'],
  ['DOC-002','아산배방LH4단지 공고문.hwp','HWP','파싱 완료','구조화 완료','2026.07.17 13:42'],
  ['DOC-003','성남낙생 A-1BL 공고문.hwpx','HWPX','처리 중','구조화 대기','2026.07.17 13:38'],
  ['DOC-004','양산시 매입임대 공고문.hwp','HWP','파싱 실패','오류','2026.07.17 13:31'],
]

function Logo({ dark = false }: { dark?: boolean }) {
  return <div className="logo-wrap"><div className={`lh-logo ${dark ? 'dark' : ''}`}><span>LH</span><i></i></div><strong>공고 AI 도우미</strong></div>
}

function Icon({ name, size = 18 }: { name: string, size?: number }) {
  const common = { size, strokeWidth: 1.9, 'aria-hidden': true as const }
  const map: Record<string, React.ReactNode> = {
    list: <List {...common}/>,
    guide: <BookOpen {...common}/>,
    glossary: <FileText {...common}/>,
    admin: <UserRound {...common}/>,
    error: <TriangleAlert {...common}/>,
    doc: <ClipboardList {...common}/>,
    logout: <LogOut {...common}/>,
    search: <Search {...common}/>,
    down: <ChevronDown {...common}/>,
    back: <ArrowLeft {...common}/>,
    ext: <ExternalLink {...common}/>,
    send: <Send {...common}/>,
    info: <Info {...common}/>,
    upload: <Upload {...common}/>,
    download: <Download {...common}/>,
    more: <MoreVertical {...common}/>,
    check: <Check {...common}/>,
    close: <X {...common}/>,
    settings: <Settings {...common}/>,
    refresh: <RefreshCw {...common}/>,
    eye: <Eye {...common}/>,
    bot: <Bot {...common}/>,
    chat: <MessageCircle {...common}/>,
    filecheck: <FileCheck2 {...common}/>,
    database: <Database {...common}/>,
    help: <CircleHelp {...common}/>,
  }
  return <span className="simple-icon">{map[name] ?? <CircleHelp {...common}/>}</span>
}

function ToastMessage({ toast }: { toast: Toast }) {
  return toast ? <div className="app-toast">{toast.message}</div> : null
}

function useToast() {
  const [toast, setToast] = useState<Toast>(null)
  const showToast = (message: string) => {
    const id = Date.now(); setToast({ message, id }); window.setTimeout(() => setToast(t => t?.id === id ? null : t), 1800)
  }
  return { toast, showToast }
}

function openLH() { window.open('https://apply.lh.or.kr/', '_blank', 'noopener,noreferrer') }

function UserSidebar({ screen, go, showToast }: { screen: Screen, go: (s: Screen) => void, showToast:(m:string)=>void }) {
  const active = screen === 'detail' ? 'list' : screen
  return <aside className="user-sidebar"><Logo/><nav>
    <button className={active==='list'?'active':''} onClick={()=>go('list')}><Icon name="list"/>공고 목록</button>
    <button className={active==='guide'?'active':''} onClick={()=>go('guide')}><Icon name="guide"/>이용 안내</button>
    <button className={active==='glossary'?'active':''} onClick={()=>go('glossary')}><Icon name="glossary"/>용어 설명</button>
  </nav><div className="side-info"><b>안내</b><p>{screen==='glossary'?'공고 관련 주요 용어와 개념을 쉽고 자세하게 설명해 드립니다.':'LH 청약플러스의 분양주택 공고를 AI가 쉽게 이해할 수 있도록 도와드립니다.'}</p><p>{screen==='glossary'?'이해가 어려운 용어를 검색하거나 목록에서 선택해 보세요.':'궁금한 내용을 채팅으로 질문하면 AI가 답변해 드립니다.'}</p><button onClick={()=>{showToast('LH 청약플러스 새 창을 엽니다.'); openLH()}}>LH 청약플러스 바로가기 <Icon name="ext"/></button></div></aside>
}

function AdminSidebar({ screen, go, showToast }: { screen: Screen, go:(s:Screen)=>void, showToast:(m:string)=>void }) {
  return <aside className="admin-sidebar"><Logo dark/><div className="admin-user"><Icon name="admin"/> 관리자</div><div className="admin-label">관리자 메뉴</div><nav>
    <button className={screen==='admin-notices'?'active':''} onClick={()=>go('admin-notices')}><Icon name="doc"/>공고 관리</button>
    <button className={screen==='admin-docs'?'active':''} onClick={()=>go('admin-docs')}><Icon name="doc"/>문서 관리</button>
    <button className={screen==='admin-errors'?'active':''} onClick={()=>go('admin-errors')}><Icon name="error"/>오류 관리</button>
  </nav><button className="logout" onClick={()=>{showToast('로그아웃되었습니다.'); go('list')}}><Icon name="logout"/>로그아웃</button></aside>
}

function StatusPill({ children }: { children:string }) {
  const cls = children.includes('실패')||children.includes('미해결')?'red':children==='공고중'||children==='수집완료'||children.includes('완료')?'green':children.includes('정정')||children.includes('예정')?'blue':children.includes('처리중')||children.includes('수집중')||children.includes('해결 중')?'orange':'gray'
  return <span className={`status-pill ${cls}`}>{children}</span>
}

function DropdownSelect({ values, value, onChange, className='', label }: { values:string[], value:string, onChange:(v:string)=>void, className?:string, label?:string }) {
  const [open,setOpen]=useState(false)
  useEffect(()=>{ if(!open) return; const close=()=>setOpen(false); const id=window.setTimeout(()=>document.addEventListener('click',close),0); return()=>{window.clearTimeout(id);document.removeEventListener('click',close)} },[open])
  return <div className={`dropdown ${className}`} onClick={e=>e.stopPropagation()}>
    <button className="dropdown-trigger" aria-haspopup="listbox" aria-expanded={open} onClick={()=>setOpen(v=>!v)}>{label&&<span className="sr-only">{label}</span>}<span>{value}</span><Icon name="down"/></button>
    {open&&<div className="dropdown-menu" role="listbox">{values.map(v=><button key={v} role="option" aria-selected={v===value} className={v===value?'selected':''} onClick={()=>{onChange(v);setOpen(false)}}>{v}{v===value&&<Icon name="check" size={15}/>}</button>)}</div>}
  </div>
}

function Pagination({ pages, page, onChange }: { pages:number, page:number, onChange:(p:number)=>void }) {
  const set=(p:number)=>onChange(Math.max(1,Math.min(pages,p)))
  return <div className="pagination"><button aria-label="첫 페이지" onClick={()=>set(1)}><ChevronsLeft size={18}/></button><button aria-label="이전 페이지" onClick={()=>set(page-1)}><ChevronLeft size={18}/></button>{Array.from({length:pages},(_,i)=><button onClick={()=>set(i+1)} className={page===i+1?'active':''} key={i}>{i+1}</button>)}<button aria-label="다음 페이지" onClick={()=>set(page+1)}><ChevronRight size={18}/></button><button aria-label="마지막 페이지" onClick={()=>set(pages)}><ChevronsRight size={18}/></button></div>
}

function ListScreen({ go, showToast }: { go:(s:Screen)=>void, showToast:(m:string)=>void }) {
  const [query,setQuery]=useState(''); const [searchQuery,setSearchQuery]=useState(''); const [region,setRegion]=useState('지역 전체'); const [status,setStatus]=useState('공고 상태 전체'); const [sort,setSort]=useState('최신순'); const [page,setPage]=useState(1)
  const pageSize=6
  const filtered=useMemo(()=>announcements.filter(a=>(!searchQuery||a.title.toLowerCase().includes(searchQuery.toLowerCase()))&&(region==='지역 전체'||a.region===region)&&(status==='공고 상태 전체'||a.status===status)).sort((a,b)=>sort==='최신순'?b.date.localeCompare(a.date):a.date.localeCompare(b.date)),[searchQuery,region,status,sort])
  const pages=Math.max(1,Math.ceil(filtered.length/pageSize)); const visible=filtered.slice((page-1)*pageSize,page*pageSize)
  useEffect(()=>{ if(page>pages) setPage(pages) },[pages,page])
  const search=()=>{setSearchQuery(query.trim());setPage(1);showToast(query.trim()?`'${query.trim()}' 검색 결과를 반영했습니다.`:'전체 공고를 표시합니다.')}
  return <UserLayout screen="list" go={go} showToast={showToast}><section className="page-head"><h1>분양주택 공고 목록</h1><p>LH 청약플러스의 분양주택 공고를 제공합니다.</p></section>
    <div className="filter-card"><div className="list-filter-row"><label className="search-long"><input value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>e.key==='Enter'&&search()} placeholder="공고명 검색"/><button onClick={search}>검색</button></label><DropdownSelect label="지역 필터" values={['지역 전체','울산광역시','충청남도','경기도','경상남도']} value={region} onChange={v=>{setRegion(v);setPage(1)}}/><DropdownSelect label="공고 상태 필터" values={['공고 상태 전체','공고중','정정공고중','마감']} value={status} onChange={v=>{setStatus(v);setPage(1)}}/><DropdownSelect label="정렬" className="sort-btn" values={['최신순','오래된순']} value={sort} onChange={v=>{setSort(v);setPage(1)}}/></div><p className="count-note"><Icon name="info"/> 총 {filtered.length}건의 공고가 있습니다. (최근 업데이트: 2026.07.17 13:50)</p></div>
    <div className="data-card announcement-table"><div className="table-head row-ann"><div>번호</div><div>공고명</div><div>지역</div><div>공고일</div><div>공고 상태</div><div></div></div>{visible.map(a=><button className="table-row row-ann" key={a.id} onClick={()=>go('detail')}><div>{a.id}</div><div className="title-cell">{a.title}</div><div>{a.region}</div><div>{a.date}</div><div><StatusPill>{a.status}</StatusPill></div><div className="chev">›</div></button>)}{visible.length===0&&<div className="empty-state">조건에 맞는 공고가 없습니다.</div>}<Pagination pages={pages} page={page} onChange={p=>{setPage(p);window.scrollTo({top:0,behavior:'smooth'});showToast(`${p}페이지로 이동했습니다.`)}}/></div>
  </UserLayout>
}

type ChatMessage={role:'user'|'ai',text:string,time:string,evidence?:boolean}
function DetailScreen({ go, showToast }: { go:(s:Screen)=>void, showToast:(m:string)=>void }) {
  const [evidence,setEvidence]=useState(false); const [origin,setOrigin]=useState(false); const [docs,setDocs]=useState(false); const [input,setInput]=useState('')
  const [messages,setMessages]=useState<ChatMessage[]>([{role:'user',text:'신청 자격을 알려줘.',time:'10:30'},{role:'ai',text:'해당 공고의 신청 자격은 다음과 같습니다.\n• 무주택 세대구성원\n• 혼인기간 7년 이내 또는 6세 이하 자녀가 있는 신혼부부\n• 월평균 소득 130% 이하\n• 총자산 3.45억원 이하\n• 자동차 가액 3,708만원 이하',time:'10:30',evidence:true},{role:'user',text:'제출 서류는 무엇인가요?',time:'10:31'},{role:'ai',text:'제출 서류는 다음과 같습니다.\n• 주민등록등본\n• 가족관계증명서\n• 소득금액증명원 등',time:'10:31'}])
  const send=()=>{const q=input.trim(); if(!q){showToast('질문을 입력해 주세요.');return} const now=new Date().toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit',hour12:false}); setMessages(m=>[...m,{role:'user',text:q,time:now}]); setInput(''); showToast('AI가 답변을 생성하고 있습니다.'); window.setTimeout(()=>setMessages(m=>[...m,{role:'ai',text:q.includes('서류')?'제출 서류는 주민등록등본, 가족관계증명서, 소득금액증명원 등이 필요합니다.':'선택한 공고문을 기준으로 확인한 결과입니다. 정확한 신청 여부는 원문 공고문의 자격 조건을 함께 확인해 주세요.',time:now,evidence:true}]),700)}
  return <UserLayout screen="detail" go={go} showToast={showToast}><button className="back-link" onClick={()=>go('list')}><Icon name="back"/> 목록으로 돌아가기</button><div className="detail-title-row"><div><h1>공고 상세 및 AI 질의응답</h1><div className="detail-ann-title"><StatusPill>공고중</StatusPill><strong>울산다운2 A-9 신혼희망타운 선착순 동호지정 공고(5년무이자 할부 및 발코니비용 무상)</strong></div><div className="meta"><span>공고일</span> 2026.05.21 <span>공고 상태</span> 공고중</div></div><div className="detail-actions"><small>* 대화 내용은 저장되지 않습니다.</small><button onClick={()=>setOrigin(true)}>원문 공고문 보기 <Icon name="ext"/></button></div></div>
    <div className="detail-grid"><div className="summary-panel"><h2>핵심 정보 요약</h2><SummaryCard icon="calendar" title="신청 일정" rows={[["공고일","2026.05.21(목)"],["접수기간","2026.05.21(목) ~ 2027.01.31(일)"],["당첨자 발표","2027.04.13(화)"],["계약체결","2027.04.19(월) ~ 2027.04.23(금)"]]}/><SummaryCard icon="home" title="공급 정보" rows={[["공급 위치","울산광역시"],["공급 세대수","15,910세대"],["주택형","55A"]]}/><SummaryCard icon="eligibility" title="신청 자격" rows={[["신청 자격","무주택 세대구성원"],["소득 기준","전년도 도시근로자 월평균 소득 130% 이하"],["자산 기준","총자산 3.45억원 이하, 자동차 3,708만원 이하"]]}/><SummaryCard icon="price" title="공급 가격 (최고가 기준)" rows={[["주택형 55A","3.78억원"]]}/><div className="summary-card documents-card"><h3><span><FileStack size={20}/></span>제출 서류</h3><ul><li>주민등록등본</li><li>가족관계증명서</li><li>소득금액증명원 등</li></ul><button onClick={()=>setDocs(true)}>상세 제출 서류 보기</button></div><p className="summary-foot">※ 핵심 정보는 공고문을 AI가 분석하여 추출한 내용으로, 실제 공고문을 원본으로 확인하세요.</p></div>
      <div className="chat-panel"><h2>AI에게 무엇이든 물어보세요</h2><p>공고에 대해 궁금한 내용을 질문하면 AI가 답변해 드립니다.</p><div className="chat-area">{messages.map((m,i)=>m.role==='user'?<div className="bubble user" key={i}>{m.text}<small>{m.time}</small></div>:<div className="bubble-row ai" key={i}><div className="ai-dot">AI</div><div className="bubble ai-bubble"><div className="preline">{m.text}</div><small>{m.time}</small>{m.evidence&&<button className="evidence-btn" onClick={()=>setEvidence(true)}>근거 문단 보기</button>}</div></div>)}</div><div className="chat-warning">AI 답변은 공고문을 기반으로 제공되며, 실제 내용과 다를 수 있습니다.<br/>정확한 내용은 원본 공고문을 확인해 주세요.</div><div className="chat-input"><input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==='Enter'&&send()} placeholder="궁금한 내용을 입력하세요."/><button onClick={send}><Icon name="send"/></button></div></div></div>
    {evidence&&<InfoModal title="답변 근거" onClose={()=>setEvidence(false)}><p className="muted">AI 답변에 사용된 원문 문단입니다.</p><div className="evidence-meta"><b>근거 유형</b><span>신청 자격</span><b>위치</b><span>공고문 신청자격 섹션</span></div><blockquote>입주자 모집공고일 현재 무주택 세대구성원으로서 신혼부부 및 예비신혼부부 자격을 충족하고, 소득 및 자산 기준을 만족하는 자를 신청 대상으로 합니다.</blockquote><button className="primary modal-origin" onClick={()=>{setEvidence(false);setOrigin(true)}}>원문 공고문 보기 <Icon name="ext"/></button></InfoModal>}
    {origin&&<InfoModal title="원문 공고문" onClose={()=>setOrigin(false)}><p>프로토타입에서는 실제 LH 원문 대신 원문 확인 흐름을 보여줍니다.</p><div className="mock-document"><b>울산다운2 A-9 신혼희망타운 입주자모집공고</b><p>신청자격, 공급일정, 제출서류 등 공식 내용은 LH 청약플러스 원문에서 확인합니다.</p></div><button className="primary modal-origin" onClick={()=>{setOrigin(false);openLH()}}>LH 청약플러스에서 확인 <Icon name="ext"/></button></InfoModal>}
    {docs&&<InfoModal title="상세 제출 서류" onClose={()=>setDocs(false)}><ul className="modal-list"><li>주민등록등본</li><li>가족관계증명서</li><li>혼인관계증명서(해당자)</li><li>소득금액증명원 또는 소득확인서류</li><li>자산 관련 증빙서류</li></ul><button className="primary modal-origin" onClick={()=>setDocs(false)}>확인</button></InfoModal>}
  </UserLayout>
}

function InfoModal({title,onClose,children}:{title:string,onClose:()=>void,children:React.ReactNode}) { return <div className="modal-backdrop" onClick={onClose}><div className="evidence-modal" onClick={e=>e.stopPropagation()}><button className="modal-close" onClick={onClose}>×</button><h2>{title}</h2>{children}</div></div> }
function SummaryCard({icon,title,rows}:{icon:string,title:string,rows:string[][]}) { const iconNode = icon==='calendar'?<CalendarDays size={20}/>:icon==='home'?<House size={20}/>:icon==='eligibility'?<BadgeCheck size={20}/>:icon==='price'?<CircleDollarSign size={20}/>:<FileText size={20}/>; return <div className="summary-card"><h3><span>{iconNode}</span>{title}</h3>{rows.map(([k,v])=><div className="summary-row" key={k}><b>{k}</b><span>{v}</span></div>)}</div> }

function GuideScreen({go,showToast}:{go:(s:Screen)=>void,showToast:(m:string)=>void}) { const steps=[['공고 목록 확인','공고 목록에서 원하는 분양주택 공고를 검색하거나 필터를 사용해 찾아보세요.','search','list'],['공고 선택','상세 내용을 확인하고 싶은 공고를 선택하세요.','document','list'],['핵심 정보 확인','AI가 공고문을 분석하여 핵심 정보를 요약해 제공합니다.','check','detail'],['AI 질문 및 확인','궁금한 내용을 질문하면 AI가 답변을 드립니다. 원문 근거도 함께 확인하세요.','chat','detail']] as const; return <UserLayout screen="guide" go={go} showToast={showToast}><section className="page-head"><h1>이용 안내</h1><p>LH 공고 AI 도우미를 쉽고 편리하게 이용하는 방법을 안내합니다.</p></section><div className="guide-flow">{steps.map((s,i)=><div className="guide-step-wrap" key={s[0]}><button className="guide-step guide-step-button" onClick={()=>go(s[3])}><span className="step-num">{i+1}</span><h2>{s[0]}</h2><p>{s[1]}</p><GuideIcon type={s[2]}/></button>{i<steps.length-1&&<div className="flow-arrow">→</div>}</div>)}</div><div className="notice-box"><h2><Icon name="info"/> 유의사항</h2><ul><li>AI가 제공하는 답변은 공고문을 기반으로 생성된 참고 정보입니다.</li><li>실제 신청 자격 및 일정 등은 반드시 원본 공고문을 확인하시기 바랍니다.</li><li>서비스 이용 중 오류나 문의사항이 있으시면 관리자에게 문의해 주세요.</li></ul></div></UserLayout> }

function GuideIcon({type}:{type:string}) { if(type==='search')return <div className="guide-icon guide-svg"><svg viewBox="0 0 120 100"><rect x="18" y="22" width="62" height="42" rx="4" fill="none" stroke="currentColor" strokeWidth="5"/><path d="M12 72h72" fill="none" stroke="currentColor" strokeWidth="5"/><circle cx="79" cy="58" r="17" fill="#fff" stroke="currentColor" strokeWidth="5"/><path d="M91 70l17 17" stroke="currentColor" strokeWidth="6"/></svg></div>; if(type==='document')return <div className="guide-icon guide-svg"><svg viewBox="0 0 120 100"><path d="M31 12h42l20 20v54H31z" fill="none" stroke="currentColor" strokeWidth="5"/><path d="M73 12v22h20M44 48h34M44 61h34M44 74h24" fill="none" stroke="currentColor" strokeWidth="4"/><path d="M88 60l18 7-10 5 5 14-7 3-6-14-8 7z" fill="#fff" stroke="currentColor" strokeWidth="4"/></svg></div>; if(type==='check')return <div className="guide-icon guide-svg"><svg viewBox="0 0 120 100"><rect x="25" y="24" width="70" height="60" rx="4" fill="none" stroke="currentColor" strokeWidth="5"/><path d="M47 51l8 8 18-20M47 70l8 8 18-20" stroke="#0d6efd" strokeWidth="5" fill="none"/><path d="M48 33h24" stroke="currentColor" strokeWidth="5"/></svg></div>; return <div className="guide-icon guide-svg"><svg viewBox="0 0 120 100"><path d="M20 30h62a10 10 0 0 1 10 10v22a10 10 0 0 1-10 10H53L36 87v-15H20a10 10 0 0 1-10-10V40a10 10 0 0 1 10-10z" fill="none" stroke="currentColor" strokeWidth="5"/><rect x="55" y="18" width="55" height="42" rx="12" fill="#0d6efd"/><circle cx="72" cy="39" r="4" fill="#fff"/><circle cx="83" cy="39" r="4" fill="#fff"/><circle cx="94" cy="39" r="4" fill="#fff"/></svg></div> }

function GlossaryScreen({ go, showToast }: { go:(s:Screen)=>void, showToast:(m:string)=>void }) {
  const [query,setQuery]=useState(''); const [page,setPage]=useState(1); const [selected,setSelected]=useState<string[]|null>(null); const pageSize=4
  const filtered=glossary.filter(g=>g[0].toLowerCase().includes(query.toLowerCase())||g[1].toLowerCase().includes(query.toLowerCase())); const pages=Math.max(1,Math.ceil(filtered.length/pageSize)); const visible=filtered.slice((page-1)*pageSize,page*pageSize)
  useEffect(()=>{setPage(1)},[query]); useEffect(()=>{if(page>pages)setPage(pages)},[pages,page])
  return <UserLayout screen="glossary" go={go} showToast={showToast}><div className="glossary-head"><section className="page-head"><h1>용어 설명</h1><p>공고 이해에 도움이 되는 주요 용어를 확인할 수 있습니다.</p></section><label className="glossary-search"><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="용어 검색"/><button aria-label="용어 검색" onClick={()=>showToast(`${filtered.length}개의 용어를 찾았습니다.`)}><Icon name="search"/></button></label></div><div className="glossary-notice"><h2><Icon name="info"/> 이용 안내</h2><ul><li>검색창에 용어를 입력하면 관련 용어를 빠르게 찾을 수 있습니다.</li><li>용어를 클릭하면 자세한 설명을 확인할 수 있습니다.</li><li>공고문 기반 용어로, 실제 신청 시에는 원문 공고를 함께 확인해 주세요.</li></ul></div><div className="glossary-table"><div className="glossary-row head"><div>용어</div><div>설명</div><div></div></div>{visible.map(g=><button className="glossary-row glossary-button" key={g[0]} onClick={()=>setSelected(g)}><div><b>{g[0]}</b></div><div>{g[1]}</div><div>›</div></button>)}{visible.length===0&&<div className="empty-state">검색 결과가 없습니다.</div>}</div><Pagination pages={pages} page={page} onChange={setPage}/>{selected&&<InfoModal title={selected[0]} onClose={()=>setSelected(null)}><p className="glossary-detail">{selected[1]}</p><button className="primary modal-origin" onClick={()=>setSelected(null)}>확인</button></InfoModal>}</UserLayout>
}

function UserLayout({screen,go,showToast,children}:{screen:Screen,go:(s:Screen)=>void,showToast:(m:string)=>void,children:React.ReactNode}) { return <div className="app-shell"><UserSidebar screen={screen} go={go} showToast={showToast}/><main className="user-main">{children}</main></div> }

function FilterBar({query,setQuery,status,setStatus,collect,setCollect,onSearch,onReset}:{query:string,setQuery:(v:string)=>void,status:string,setStatus:(v:string)=>void,collect:string,setCollect:(v:string)=>void,onSearch:()=>void,onReset:()=>void}) { const [date,setDate]=useState(''); return <div className="filters admin-filters"><label className="searchbox"><input value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>e.key==='Enter'&&onSearch()} placeholder="공고명 검색"/><Icon name="search"/></label><DropdownSelect label="공고 상태" values={['공고 상태 전체','공고중','공고예정']} value={status} onChange={setStatus}/><DropdownSelect label="수집 상태" values={['수집 상태 전체','수집완료','수집중','수집실패','미수집']} value={collect} onChange={setCollect}/><label className="date-filter"><span>{date||'등록일 선택'}</span><input aria-label="등록일 선택" type="date" value={date} onChange={e=>setDate(e.target.value)}/></label><button className="primary" onClick={onSearch}>검색</button><button onClick={()=>{setDate('');onReset()}}>초기화</button></div> }

function AdminNotices({go,showToast}:{go:(s:Screen)=>void,showToast:(m:string)=>void}) { const [query,setQuery]=useState(''); const [status,setStatus]=useState('공고 상태 전체'); const [collect,setCollect]=useState('수집 상태 전체'); const [page,setPage]=useState(1); const [action,setAction]=useState<string[]|null>(null); const [collectModal,setCollectModal]=useState(false); const rows=adminNoticeRows.filter(r=>(!query||r[1].includes(query))&&(status==='공고 상태 전체'||r[6]===status)&&(collect==='수집 상태 전체'||r[5]===collect)); const pageSize=5; const pages=Math.max(1,Math.ceil(rows.length/pageSize)); const visibleRows=rows.slice((page-1)*pageSize,page*pageSize); const download=()=>downloadCsv('notices.csv',[['No','공고명','지역','공고일','접수기간','수집 상태','공고 상태','데이터 상태'],...adminNoticeRows]); return <AdminLayout screen="admin-notices" go={go} showToast={showToast}><AdminTop title="공고 관리" subtitle="수집된 공고 목록과 기본 정보를 확인하고 관리할 수 있습니다." showToast={showToast}/><FilterBar query={query} setQuery={setQuery} status={status} setStatus={setStatus} collect={collect} setCollect={setCollect} onSearch={()=>showToast(`${rows.length}건을 조회했습니다.`)} onReset={()=>{setQuery('');setStatus('공고 상태 전체');setCollect('수집 상태 전체');showToast('필터를 초기화했습니다.')}}/><div className="admin-toolbar"><b>총 {rows.length}건</b><div><button onClick={download}><Icon name="download"/> 목록 다운로드</button><button className="primary" onClick={()=>setCollectModal(true)}><span className="plus-text">＋</span> 공고 수집</button></div></div><div className="admin-table notice-admin"><div className="admin-row head"><div>No.</div><div>공고명</div><div>지역</div><div>공고일</div><div>접수기간</div><div>수집 상태</div><div>공고 상태</div><div>데이터 상태</div><div>작업</div></div>{visibleRows.map(r=><div className="admin-row" key={r[0]}>{r.map((c,i)=><div key={i}>{i>=5&&i<=7&&c!=='-'?<StatusPill>{c}</StatusPill>:<span className={i===1?'wrap-cell':''}>{c}</span>}</div>)}<div><button className="icon-action" onClick={()=>setAction(r)}><Icon name="more"/></button></div></div>)}</div><Pagination pages={pages} page={page} onChange={setPage}/><p className="admin-note"><Icon name="info"/> 수집 실패 시, [작업] 메뉴에서 재수집을 진행할 수 있습니다.</p>{action&&<InfoModal title="공고 작업" onClose={()=>setAction(null)}><p><b>{action[1]}</b></p><div className="action-stack"><button onClick={()=>{showToast('공고 상세를 확인했습니다.');setAction(null)}}>상세 정보 보기</button><button onClick={()=>{showToast('재수집 작업을 시작했습니다.');setAction(null)}}>재수집</button><button onClick={()=>{showToast('분석 재처리를 시작했습니다.');setAction(null)}}>분석 재처리</button></div></InfoModal>}{collectModal&&<InfoModal title="공고 수집" onClose={()=>setCollectModal(false)}><p>LH 청약플러스의 신규 공고를 수집하는 프로토타입 동작입니다.</p><button className="primary modal-origin" onClick={()=>{setCollectModal(false);showToast('공고 수집 작업을 시작했습니다.')}}>수집 시작</button></InfoModal>}</AdminLayout> }

function AdminDocs({go,showToast}:{go:(s:Screen)=>void,showToast:(m:string)=>void}) { const [page,setPage]=useState(1); const [selected,setSelected]=useState<string[]|null>(null); const [uploaded,setUploaded]=useState<string[]>([]); const pageSize=3; const allRows=[...uploaded.map((name,i)=>[`UP-${i+1}`,name,name.toLowerCase().endsWith('.hwpx')?'HWPX':'HWP','업로드 완료','구조화 대기',new Date().toLocaleString('ko-KR')]),...documentRows]; const pages=Math.max(1,Math.ceil(allRows.length/pageSize)); const visibleRows=allRows.slice((page-1)*pageSize,page*pageSize); return <AdminLayout screen="admin-docs" go={go} showToast={showToast}><AdminTop title="문서 관리" subtitle="수집된 HWP/HWPX 문서의 파싱 및 구조화 상태를 확인할 수 있습니다." showToast={showToast}/><div className="admin-toolbar"><b>총 {allRows.length}건</b><div><button onClick={()=>downloadCsv('documents.csv',[['ID','파일명','형식','파싱 상태','구조화 상태','업데이트'],...allRows])}><Icon name="download"/> 목록 다운로드</button><label className="primary file-upload-button"><Icon name="upload"/> 문서 업로드<input type="file" accept=".hwp,.hwpx" multiple onChange={e=>{const names=Array.from(e.target.files??[]).map(f=>f.name); if(names.length){setUploaded(u=>[...names,...u]);setPage(1);showToast(`${names.length}개 문서를 업로드 목록에 추가했습니다.`)} e.currentTarget.value='' }}/></label></div></div><div className="admin-table docs-admin"><div className="admin-row head"><div>ID</div><div>파일명</div><div>형식</div><div>파싱 상태</div><div>구조화 상태</div><div>업데이트</div><div>작업</div></div>{visibleRows.map(r=><div className="admin-row" key={r[0]}>{r.map((c,i)=><div key={i}>{i===3||i===4?<StatusPill>{c}</StatusPill>:c}</div>)}<div><button className="small-btn" onClick={()=>setSelected(r)}>상세보기</button></div></div>)}</div><Pagination pages={pages} page={page} onChange={setPage}/>{selected&&<InfoModal title="문서 상세" onClose={()=>setSelected(null)}><p><b>{selected[1]}</b></p><p>형식: {selected[2]} / 파싱: {selected[3]} / 구조화: {selected[4]}</p><div className="action-stack"><button onClick={()=>showToast('문서 원본 미리보기를 열었습니다.')}>원본 미리보기</button><button onClick={()=>{showToast('재처리를 시작했습니다.');setSelected(null)}}>재처리</button></div></InfoModal>}</AdminLayout> }

function AdminErrors({go,showToast}:{go:(s:Screen)=>void,showToast:(m:string)=>void}) { const [type,setType]=useState('오류 유형 전체'); const [section,setSection]=useState('발생 구간 전체'); const [status,setStatus]=useState('상태 전체'); const [query,setQuery]=useState(''); const [page,setPage]=useState(1); const [selected,setSelected]=useState<string[]|null>(null); const rows=errorRows.filter(r=>(!query||r[4].includes(query)||r[5].includes(query))&&(type==='오류 유형 전체'||r[2]===type)&&(section==='발생 구간 전체'||r[3]===section)&&(status==='상태 전체'||r[6]===status)); const pageSize=5; const pages=Math.max(1,Math.ceil(rows.length/pageSize)); const visibleRows=rows.slice((page-1)*pageSize,page*pageSize); return <AdminLayout screen="admin-errors" go={go} showToast={showToast}><AdminTop title="오류 관리" subtitle="공고 수집, 문서 처리 및 분석 과정에서 발생한 오류를 확인하고 관리할 수 있습니다." showToast={showToast}/><div className="filters error-filters"><label className="searchbox"><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="오류 내용 또는 공고명 검색"/><Icon name="search"/></label><DropdownSelect values={['오류 유형 전체','문서 가공','분석 처리','수집','문서 저장']} value={type} onChange={setType}/><DropdownSelect values={['발생 구간 전체','문서 처리','AI 분석','공고 수집']} value={section} onChange={setSection}/><DropdownSelect values={['상태 전체','미해결','해결 중','해결 완료']} value={status} onChange={setStatus}/><label className="date-filter">발생일 선택 <input type="date" onChange={()=>{setPage(1);showToast('발생일 필터를 선택했습니다.')}}/></label><button className="primary" onClick={()=>showToast(`${rows.length}건을 조회했습니다.`)}>검색</button><button onClick={()=>{setQuery('');setType('오류 유형 전체');setSection('발생 구간 전체');setStatus('상태 전체');showToast('필터를 초기화했습니다.')}}>초기화</button></div><div className="error-summary"><Stat label="전체 오류" value="26건" tone="blue" icon="file"/><Stat label="미해결" value="10건" tone="red" icon="alert"/><Stat label="해결 중" value="5건" tone="orange" icon="loading"/><Stat label="해결 완료" value="11건" tone="green" icon="done"/><button className="download-btn" onClick={()=>downloadCsv('errors.csv',[['No','발생 일시','오류 유형','발생 구간','공고명','오류 내용','상태','조치 내용'],...errorRows])}><Icon name="download"/> 목록 다운로드</button></div><div className="admin-table error-admin"><div className="admin-row head"><div>No.</div><div>발생 일시</div><div>오류 유형</div><div>발생 구간</div><div>공고명</div><div>오류 내용</div><div>상태</div><div>조치 내용</div><div>작업</div></div>{visibleRows.map(r=><div className="admin-row" key={r[0]}>{r.map((c,i)=><div key={i}>{i===2||i===6?<StatusPill>{c}</StatusPill>:c}</div>)}<div><button className="small-btn" onClick={()=>setSelected(r)}>상세보기</button></div></div>)}</div><Pagination pages={pages} page={page} onChange={setPage}/><p className="admin-note"><Icon name="info"/> 상태가 '미해결' 또는 '해결 중'인 오류는 우선적으로 조치해 주세요.</p>{selected&&<InfoModal title="오류 상세" onClose={()=>setSelected(null)}><p><b>{selected[5]}</b></p><p>발생 구간: {selected[3]} / 상태: {selected[6]}</p><p>조치 내용: {selected[7]}</p><div className="action-stack"><button onClick={()=>{showToast('재처리 작업을 시작했습니다.');setSelected(null)}}>재처리</button><button onClick={()=>{showToast('해결 완료로 변경했습니다.');setSelected(null)}}>해결 완료 처리</button></div></InfoModal>}</AdminLayout> }

function downloadCsv(name:string, rows:string[][]){ const csv=rows.map(r=>r.map(v=>`"${String(v).replaceAll('"','""')}"`).join(',')).join('\n'); const blob=new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'}); const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=name; a.click(); URL.revokeObjectURL(a.href) }
function Stat({label,value,tone,icon}:{label:string,value:string,tone:string,icon:string}) { const iconNode = icon==='file'?<FileText size={28}/>:icon==='alert'?<TriangleAlert size={28}/>:icon==='loading'?<RefreshCw size={28}/>:<BadgeCheck size={28}/>; return <div className="stat-card"><div><span>{label}</span><strong className={tone}>{value}</strong></div><div className={`stat-icon ${tone}`}>{iconNode}</div></div> }
function AdminTop({title,subtitle,showToast}:{title:string,subtitle:string,showToast:(m:string)=>void}) { const [open,setOpen]=useState(false); return <><button className="admin-user-top" onClick={()=>setOpen(!open)}>최가람 관리자 <ChevronDown size={16}/></button>{open&&<div className="admin-user-menu"><button onClick={()=>{setOpen(false);showToast('관리자 프로필을 확인했습니다.')}}>프로필</button><button onClick={()=>{setOpen(false);showToast('설정 화면은 프로토타입입니다.')}}>설정</button></div>}<section className="admin-head"><h1>{title}</h1><p>{subtitle}</p></section></> }
function AdminLayout({screen,go,showToast,children}:{screen:Screen,go:(s:Screen)=>void,showToast:(m:string)=>void,children:React.ReactNode}) { return <div className="app-shell admin-shell"><AdminSidebar screen={screen} go={go} showToast={showToast}/><main className="admin-main">{children}</main></div> }

export default function App(){
  const routeToScreen=()=>{const p=window.location.pathname;if(p.includes('admin/errors'))return 'admin-errors' as Screen;if(p.includes('admin/docs'))return 'admin-docs' as Screen;if(p.includes('admin'))return 'admin-notices' as Screen;if(p.includes('guide'))return 'guide' as Screen;if(p.includes('glossary'))return 'glossary' as Screen;if(p.includes('detail'))return 'detail' as Screen;return 'list' as Screen}
  const initial=useMemo<Screen>(routeToScreen,[]); const [screen,setScreen]=useState<Screen>(initial); const {toast,showToast}=useToast()
  const go=(s:Screen)=>{setScreen(s);const map:Record<Screen,string>={list:'/',detail:'/detail',guide:'/guide',glossary:'/glossary','admin-notices':'/admin','admin-docs':'/admin/docs','admin-errors':'/admin/errors'};window.history.pushState({},'',map[s]);window.scrollTo(0,0)}
  useEffect(()=>{const onPop=()=>setScreen(routeToScreen());window.addEventListener('popstate',onPop);return()=>window.removeEventListener('popstate',onPop)},[])
  return <>{screen==='detail'?<DetailScreen go={go} showToast={showToast}/>:screen==='guide'?<GuideScreen go={go} showToast={showToast}/>:screen==='glossary'?<GlossaryScreen go={go} showToast={showToast}/>:screen==='admin-notices'?<AdminNotices go={go} showToast={showToast}/>:screen==='admin-docs'?<AdminDocs go={go} showToast={showToast}/>:screen==='admin-errors'?<AdminErrors go={go} showToast={showToast}/>:<ListScreen go={go} showToast={showToast}/>}<ToastMessage toast={toast}/></>
}
