import { NavLink, useNavigate } from "react-router-dom";
import { clearToken } from "../App";

const navItems = [
  { to: "/dashboard", label: "仪表盘" },
  { to: "/users", label: "用户管理" },
  { to: "/api-keys", label: "API 密钥" },
  { to: "/usage", label: "用量查询" },
];

export default function Sidebar() {
  const navigate = useNavigate();

  const handleLogout = () => {
    clearToken();
    navigate("/login");
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">xwawa Admin</div>
      <ul className="sidebar-nav">
        {navItems.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
      <div style={{ padding: "24px", borderTop: "1px solid rgba(255,255,255,0.1)", marginTop: "auto" }}>
        <button className="btn btn-secondary" style={{ width: "100%" }} onClick={handleLogout}>
          退出登录
        </button>
      </div>
    </aside>
  );
}
