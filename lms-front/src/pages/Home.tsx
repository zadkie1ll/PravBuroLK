import { useNavigate } from 'react-router-dom';
import './Home.css';

const Home = () => {
  const navigate = useNavigate()
  return (
    <div className="home">
      <div className="home-card">
        <img
          src="/pravburo_logo.png"
          alt="ПравБюро"
          className="logo"
        />

        <h1>ПравБюро</h1>
        <p className="subtitle">
          Обучающие курсы и личный кабинет
        </p>

        <div className="buttons">
          <button onClick={()=>navigate('/dashboard', {replace: true})}className="primary">Пройти курсы</button>
          <button onClick={()=>navigate('/auth', {replace: true})} className="secondary">Личный кабинет</button>
        </div>
      </div>
    </div>
  );
};

export default Home;
