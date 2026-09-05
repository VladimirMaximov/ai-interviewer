import axios from 'axios';

// Keep local development working even when the dev server was started before
// the proxy setting was added. Deployments can override this explicitly.
const API_URL = process.env.REACT_APP_API_URL
  || (process.env.NODE_ENV === 'development' ? 'http://127.0.0.1:8000/api' : '/api');

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
