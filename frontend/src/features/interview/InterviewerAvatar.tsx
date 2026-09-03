export function InterviewerAvatar({ speaking, compact = false }: { speaking: boolean; compact?: boolean }) {
  return <div className={`interviewer-avatar ${compact ? "interviewer-avatar--compact" : ""} ${speaking ? "interviewer-avatar--speaking" : ""}`} aria-label={speaking ? "Аватар озвучивает вопрос" : "Аватар интервьюера"}>
    <div className="avatar-halo" />
    <div className="avatar-head"><span className="avatar-eye avatar-eye--left" /><span className="avatar-eye avatar-eye--right" /><span className="avatar-mouth" /></div>
    <div className="avatar-body" />
    <span className="avatar-status">{speaking ? "Говорит" : "Интервьюер"}</span>
  </div>;
}
