import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './App.css'
import Home from './pages/Home'
import Auth from './pages/Auth'
import Dashboard from './pages/Dashboard'
import CourseDetails from './components/CourseDetails'

function App() {
  const basename = (import.meta.env.VITE_APP_BASENAME as string | undefined)?.trim() || '/'

  return(
    <BrowserRouter basename={basename}>
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
