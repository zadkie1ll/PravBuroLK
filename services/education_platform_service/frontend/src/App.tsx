import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './App.css'
import Home from './pages/Home'
import Auth from './pages/Auth'
import Dashboard from './pages/Dashboard'
import CourseDetails from './components/CourseDetails'
import TestEdit from './pages/hr/TestEdit'
import Trainees from './pages/hr/Trainees'
import TraineeCreate from './pages/hr/TraineeCreate'
import TraineeDetail from './pages/hr/TraineeDetail'
import EducationAdmin from './pages/EducationAdmin'

function App() {
  return(
    <BrowserRouter basename={import.meta.env.BASE_URL}>
    <Routes>
      <Route path='/' element={<Home/>}/>
      <Route path='/auth' element={<Auth/>}/>
      <Route path='/dashboard' element={<Dashboard/>}/>
      <Route path='/course/:id' element={<CourseDetails/>}/>
      <Route path='/admin' element={<EducationAdmin/>}/>
      <Route path='/admin/module/:id/test' element={<TestEdit/>}/>
      <Route path='/admin/trainees' element={<Trainees/>}/>
      <Route path='/admin/trainees/new' element={<TraineeCreate/>}/>
      <Route path='/admin/trainees/:id' element={<TraineeDetail/>}/>
    </Routes>
    </BrowserRouter>
  )
}

export default App
