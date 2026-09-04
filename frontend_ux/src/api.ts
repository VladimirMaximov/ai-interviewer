import axios from 'axios';

// Мок-данные
const MOCK_DATA: any = {
  users: [
    { id: '1', username: 'interviewer', role: 'interviewer' },
    { id: '2', username: 'candidate', role: 'candidate' },
    { id: '3', username: 'manager', role: 'hiring_manager' }
  ],
  vacancies: [
    { 
      id: '1', 
      title: 'Middle Python разработчик', 
      description: 'Разработка бэкенда на Python', 
      questions: ['Расскажите о опыте работы с Django', 'Как тестируете код?'] 
    },
    { 
      id: '2', 
      title: 'Junior Data Scientist', 
      description: 'Анализ данных и ML', 
      questions: ['Что такое переобучение?', 'Как работаете с данными?'] 
    },
    { 
      id: '3', 
      title: 'Senior React Developer', 
      description: 'Фронтенд разработка на React', 
      questions: ['Что такое хуки?', 'Как управляете состоянием?'] 
    }
  ],
  leaderboardData: {
    '1': [
      { name: 'Анна С.', score: 92, recruiterScore: 85, managerScore: 88, comment: 'Отличные знания Python', date: '2024-01-15' },
      { name: 'Михаил К.', score: 87, recruiterScore: 80, managerScore: 75, comment: 'Хороший опыт', date: '2024-01-14' },
      { name: 'Екатерина П.', score: 81, recruiterScore: 70, managerScore: 78, comment: 'Нужно подтянуть алгоритмы', date: '2024-01-13' }
    ],
    '2': [
      { name: 'Дмитрий В.', score: 76, recruiterScore: 80, managerScore: 72, comment: 'Хорошо знает статистику', date: '2024-01-12' }
    ],
    '3': [
      { name: 'Сергей М.', score: 68, recruiterScore: 65, managerScore: 70, comment: 'Знает React', date: '2024-01-10' }
    ]
  }
};

// API с мок-данными
const api = {
  post: async (url: string, data?: any): Promise<any> => {
    console.log('POST:', url, data);
    
    if (url === '/login') {
      const user = MOCK_DATA.users.find((u: any) => u.username === data.username);
      if (user && data.password === '1234') {
        return { data: { token: 'mock-token-123', user } };
      }
      throw { response: { data: { detail: 'Неверный логин или пароль' } } };
    }
    
    if (url === '/register') {
      const newUser = { id: String(Date.now()), username: data.username, role: data.role };
      MOCK_DATA.users.push(newUser);
      return { data: { success: true, user: newUser } };
    }
    
    if (url === '/vacancies') {
      if (data) {
        const newVacancy = {
          id: String(Date.now()),
          title: data.title,
          description: data.description,
          questions: data.questions || []
        };
        MOCK_DATA.vacancies.push(newVacancy);
        return { data: newVacancy };
      }
      return { data: MOCK_DATA.vacancies };
    }
    
    if (url.startsWith('/vacancies/')) {
      const id = url.split('/')[2];
      if (data) {
        const index = MOCK_DATA.vacancies.findIndex((v: any) => v.id === id);
        if (index !== -1) {
          MOCK_DATA.vacancies[index] = { ...MOCK_DATA.vacancies[index], ...data };
          return { data: { success: true } };
        }
      }
    }
    
    return { data: {} };
  },
  
  get: async (url: string): Promise<any> => {
    console.log('GET:', url);
    
    if (url === '/vacancies') {
      return { data: MOCK_DATA.vacancies };
    }
    
    if (url.startsWith('/vacancies/')) {
      const id = url.split('/')[2];
      const vacancy = MOCK_DATA.vacancies.find((v: any) => v.id === id);
      if (vacancy) return { data: vacancy };
      throw { response: { status: 404, data: { detail: 'Вакансия не найдена' } } };
    }
    
    if (url.startsWith('/leaderboard/')) {
      const id = url.split('/')[2];
      return { data: MOCK_DATA.leaderboardData[id] || [] };
    }
    
    return { data: {} };
  },
  
  put: async (url: string, data: any): Promise<any> => {
    console.log('PUT:', url, data);
    const id = url.split('/')[2];
    const index = MOCK_DATA.vacancies.findIndex((v: any) => v.id === id);
    if (index !== -1) {
      MOCK_DATA.vacancies[index] = { ...MOCK_DATA.vacancies[index], ...data };
      return { data: { success: true } };
    }
    throw { response: { status: 404, data: { detail: 'Вакансия не найдена' } } };
  }
};

export default api;