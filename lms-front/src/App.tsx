import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './App.css'
import Home from './pages/Home'
import Auth from './pages/Auth'
import Dashboard from './pages/Dashboard'
import CourseDetails from './components/CourseDetails'
function App() {
  return(
    <BrowserRouter>
    <Routes>
      <Route path='/' element={<Home/>}/>
      <Route path='/auth' element={<Auth/>}/>
      <Route path='/dashboard' element={<Dashboard/>}/>
      <Route path='/course/:id' element={<CourseDetails/>}/>
    </Routes>
    </BrowserRouter>
  )
}

export default App
