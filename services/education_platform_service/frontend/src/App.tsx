import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './App.css'
import Home from './pages/Home'
import Auth from './pages/Auth'
import Dashboard from './pages/Dashboard'
import CourseDetails from './components/CourseDetails'
import HrDashboard from './pages/hr/HrDashboard'
import TestEdit from './pages/hr/TestEdit'
import Trainees from './pages/hr/Trainees'
import TraineeCreate from './pages/hr/TraineeCreate'
import TraineeDetail from './pages/hr/TraineeDetail'

function App() {
  return(
    <BrowserRouter basename={import.meta.env.BASE_URL}>
    <Routes>
      <Route path='/' element={<Home/>}/>
      <Route path='/auth' element={<Auth/>}/>
      <Route path='/dashboard' element={<Dashboard/>}/>
      <Route path='/course/:id' element={<CourseDetails/>}/>
      <Route path='/hr' element={<HrDashboard/>}/>
      <Route path='/hr/module/:id/test' element={<TestEdit/>}/>
      <Route path='/hr/trainees' element={<Trainees/>}/>
      <Route path='/hr/trainees/new' element={<TraineeCreate/>}/>
      <Route path='/hr/trainees/:id' element={<TraineeDetail/>}/>
    </Routes>
    </BrowserRouter>
  )
}

export default App
