import { useNavigate } from 'react-router-dom';
import './Home.css';

const Home = () => {
  const navigate = useNavigate()
  const logoSrc = `${import.meta.env.BASE_URL}pravburo_logo.png`

  return (
    <div className="home">
      <div className="home-card">
        <img
          src={logoSrc}
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
