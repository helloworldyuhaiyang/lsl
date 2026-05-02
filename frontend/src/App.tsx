import { HashRouter, Routes, Route } from 'react-router-dom';
import { AppProvider } from '@/context/AppContext';
import { TopNav } from '@/components/TopNav';
import { Dashboard } from '@/pages/Dashboard';
import { CreateSession } from '@/pages/CreateSession';
import { SessionDetail } from '@/pages/SessionDetail';
import { Revise } from '@/pages/Revise';
import { Listening } from '@/pages/Listening';
import { NotFound } from '@/pages/NotFound';

function App() {
  return (
    <AppProvider>
      <HashRouter>
        <div className="min-h-screen bg-slate-50 flex flex-col">
          <TopNav />
          <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
            <div className="max-w-[900px] mx-auto">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/create" element={<CreateSession />} />
                <Route path="/session/:id" element={<SessionDetail />} />
                <Route path="/session/:id/revise" element={<Revise />} />
                <Route path="/session/:id/listening" element={<Listening />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </div>
          </main>
        </div>
      </HashRouter>
    </AppProvider>
  );
}

export default App;
