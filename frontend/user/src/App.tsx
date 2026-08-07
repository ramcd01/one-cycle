import { useState } from "react";
import { ListScreen } from "./components/screens/ListScreen";
import { DetailScreen } from "./components/screens/DetailScreen";
import { GuideScreen } from "./components/screens/GuideScreen";
import { GlossaryScreen } from "./components/screens/GlossaryScreen";

type Screen = "list" | "detail" | "guide" | "glossary" | "admin-notices" | "admin-docs" | "admin-errors";
type Toast = { message: string; id: number } | null;

// 💡 백엔드 연동 시 사용할 서버 주소 (현재는 미연결 상태로 유지)
export const API_BASE_URL = "http://localhost:8000/api"; //실제 백엔드 서버 주소로 변경 필요 REMOVED

function useToast() {
  const [toast, setToast] = useState<Toast>(null);
  const showToast = (message: string) => {
    const id = Date.now();
    setToast({ message, id });
    window.setTimeout(() => setToast((t) => (t?.id === id ? null : t)), 1800);
  };
  return { toast, showToast };
}

export default function App() {
  const [screen, setScreen] = useState<Screen>("list");
  
  // 💡 기존처럼 선택된 공고 객체를 통째로 저장하여 즉시 전달
  const [selectedNotice, setSelectedNotice] = useState<any>(null);
  const { toast, showToast } = useToast();

  const go = (s: Screen, noticeData?: any) => {
    if (noticeData) {
      setSelectedNotice(noticeData);
    }
    setScreen(s);
    window.scrollTo(0, 0);
  };

  const ToastMessage = () => toast ? (
    <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-[9999] bg-slate-800 text-white px-5 py-3 rounded-xl shadow-xl text-sm font-medium animate-[toastIn_0.2s_ease-out]">
      {toast.message}
    </div>
  ) : null;

  const renderScreen = () => {
    switch (screen) {
      case "detail":
        return <DetailScreen go={go} showToast={showToast} notice={selectedNotice} />;
      case "guide":
        return <GuideScreen go={go} showToast={showToast} />;
      case "glossary":
        return <GlossaryScreen go={go} showToast={showToast} />;
      case "list":
      default:
        return <ListScreen go={go} showToast={showToast} />;
    }
  };

  return (
    <>
      {renderScreen()}
      <ToastMessage />
    </>
  );
}