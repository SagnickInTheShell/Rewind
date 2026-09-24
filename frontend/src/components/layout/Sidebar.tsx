import { Link, useLocation } from "react-router-dom";
import {
  Home,
  Activity,
  RotateCcw,
  BarChart3,
  Settings as SettingsIcon,
} from "lucide-react";

interface NavItem {
  name: string;
  path: string;
  icon: typeof Home;
}

const NAV_ITEMS: NavItem[] = [
  { name: "Home", path: "/", icon: Home },
  { name: "Analyze", path: "/analysis", icon: Activity },
  { name: "Rewind", path: "/rewind", icon: RotateCcw },
  { name: "Insights", path: "/insights", icon: BarChart3 },
];

export function Sidebar() {
  const location = useLocation();

  return (
    <aside className="flex w-60 flex-col justify-between border-r border-[#1E2633] bg-[#0B0F15] px-4 py-6 select-none shrink-0 min-h-screen">
      <div className="flex flex-col gap-8">
        {/* REWIND Logo */}
        <Link to="/" className="flex flex-col group px-2">
          <div className="flex items-center">
            <span className="text-2xl font-black tracking-widest text-[#FF3B5C]">
              RE
            </span>
            <span className="text-2xl font-black tracking-widest text-white">
              WIND
            </span>
          </div>
          <span className="text-[11px] font-medium tracking-wide text-gray-500 group-hover:text-gray-400 transition-colors mt-0.5">
            Reconstruct. Rewind. Prevent.
          </span>
        </Link>

        {/* Navigation Items */}
        <nav className="flex flex-col gap-1.5">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.path === "/"
                ? location.pathname === "/"
                : location.pathname.startsWith(item.path);

            return (
              <Link
                key={item.name}
                to={item.path}
                className={`flex items-center gap-3.5 px-4 py-3 rounded-xl font-medium text-sm transition-all duration-200 ${
                  isActive
                    ? "bg-[#251219] text-[#FF3B5C] border border-[#FF3B5C]/30 shadow-md shadow-[#FF3B5C]/10 font-semibold"
                    : "text-[#8B98A5] hover:bg-[#121821] hover:text-[#E6EDF3]"
                }`}
              >
                <Icon
                  className={`w-5 h-5 transition-transform duration-200 ${
                    isActive ? "scale-105 stroke-[2.25]" : "stroke-[1.75]"
                  }`}
                />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Bottom Settings Link */}
      <div className="pt-4 border-t border-[#1E2633]">
        <Link
          to="/upload"
          className="flex items-center gap-3.5 px-4 py-3 rounded-xl font-medium text-sm text-[#8B98A5] hover:bg-[#121821] hover:text-[#E6EDF3] transition-all"
        >
          <SettingsIcon className="w-5 h-5 stroke-[1.75]" />
          <span>Settings</span>
        </Link>
      </div>
    </aside>
  );
}
