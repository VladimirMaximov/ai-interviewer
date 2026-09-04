export interface User {
  id: string;
  username: string;
  role: 'interviewer' | 'candidate' | 'hiring_manager';
}

export interface Vacancy {
  id: string;
  title: string;
  description: string;
  questions: string[];
}

export interface LeaderboardItem {
  name: string;
  score: number;
}