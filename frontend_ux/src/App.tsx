import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Homepage from './pages/Homepage';
import Vacancy from './pages/Vacancy';
import Leaderboard from './pages/Leaderboard';
import CandidateDetails from './pages/CandidateDetails';
import 'bootstrap/dist/css/bootstrap.min.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" />} />
        <Route path="/login" element={<Login />} />
        <Route path="/homepage" element={<Homepage />} />
        <Route path="/vacancy/:id" element={<Vacancy />} />
        <Route path="/vacancy/new" element={<Vacancy />} />
        <Route path="/leaderboard/:vacancyId" element={<Leaderboard />} />
        <Route path="/leaderboard/:vacancyId/candidate/:candidateId" element={<CandidateDetails />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
