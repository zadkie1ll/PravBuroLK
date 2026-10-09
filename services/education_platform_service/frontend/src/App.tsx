import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './App.css'
import Home from './pages/Home'
import Auth from './pages/Auth'
import Dashboard from './pages/Dashboard'
import CourseDetails from './components/CourseDetails'

function App() {
  return(
    <BrowserRouter basename={import.meta.env.BASE_URL}>
    <Routes>
      <Route path='/' element={<Home/>}/>
      <Route path='/auth' element={<Auth/>}/>
      <Route path='/dashboard' element={<Dashboard/>}/>
      <Route path='/course/:id' element={<CourseDetails/>}/>
      <Route path='*' element={<Navigate to='/dashboard' replace/>}/>
    </Routes>
    </BrowserRouter>
  )
}

export default App
