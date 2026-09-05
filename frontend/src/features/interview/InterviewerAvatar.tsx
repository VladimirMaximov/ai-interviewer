type InterviewerAvatarProps = {
  speaking: boolean;
  compact?: boolean;
  idleSrc?: string;
  speakingSrc?: string;
};

export function InterviewerAvatar({
  speaking,
  compact = false,
  idleSrc,
  speakingSrc,
}: InterviewerAvatarProps) {
  if (idleSrc && speakingSrc) {
    return <div className={`interviewer-avatar interviewer-avatar--frames ${compact ? "interviewer-avatar--compact" : ""} ${speaking ? "interviewer-avatar--speaking" : ""}`} aria-label={speaking ? "Аватар озвучивает вопрос" : "Аватар интервьюера"}>
      <img className="interviewer-avatar-frame interviewer-avatar-frame--idle" src={idleSrc} alt="" />
      <img className="interviewer-avatar-frame interviewer-avatar-frame--speaking" src={speakingSrc} alt="" />
      <span className="avatar-status">Интервьюер</span>
    </div>;
  }
  return <div className={`interviewer-avatar ${compact ? "interviewer-avatar--compact" : ""} ${speaking ? "interviewer-avatar--speaking" : ""}`} aria-label={speaking ? "Аватар озвучивает вопрос" : "Аватар интервьюера"}>
    <div className="avatar-halo" />
    <div className="avatar-head"><span className="avatar-eye avatar-eye--left" /><span className="avatar-eye avatar-eye--right" /><span className="avatar-mouth" /></div>
    <div className="avatar-body" />
    <span className="avatar-status">{speaking ? "Говорит" : "Интервьюер"}</span>
  </div>;
}
