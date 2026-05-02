import React, { createContext, useContext, useReducer, useCallback, useEffect } from 'react';
import type { AppState, AppAction, Session } from '@/types';
import { listSessions } from '@/lib/api/sessions';
import { mapSessionItem } from '@/lib/domain';

const initialState: AppState = {
  sessions: [],
  currentSession: null,
  loading: false,
  error: null,
};

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_SESSIONS':
      return { ...state, sessions: action.payload };
    case 'SET_CURRENT_SESSION':
      return { ...state, currentSession: action.payload };
    case 'ADD_SESSION':
      return { ...state, sessions: [action.payload, ...state.sessions] };
    case 'UPDATE_SESSION':
      return {
        ...state,
        sessions: state.sessions.map(s => s.id === action.payload.id ? action.payload : s),
        currentSession: state.currentSession?.id === action.payload.id ? action.payload : state.currentSession,
      };
    case 'DELETE_SESSION':
      return {
        ...state,
        sessions: state.sessions.filter(s => s.id !== action.payload),
      };
    case 'UPDATE_REVISION':
      return {
        ...state,
        sessions: state.sessions.map(s =>
          s.id === action.payload.sessionId ? { ...s, revision: action.payload.revision } : s
        ),
        currentSession: state.currentSession?.id === action.payload.sessionId
          ? { ...state.currentSession, revision: action.payload.revision }
          : state.currentSession,
      };
    case 'SET_LOADING':
      return { ...state, loading: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload };
    default:
      return state;
  }
}

interface AppContextType {
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
  getSessionById: (id: string) => Session | undefined;
  refreshSessions: () => Promise<void>;
}

const AppContext = createContext<AppContextType | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  const refreshSessions = useCallback(async () => {
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      const items = await listSessions({ limit: 100 });
      dispatch({ type: 'SET_SESSIONS', payload: items.map(mapSessionItem) });
    } catch (error) {
      dispatch({
        type: 'SET_ERROR',
        payload: error instanceof Error ? error.message : 'Failed to load sessions',
      });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, []);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  const getSessionById = useCallback((id: string) => {
    return state.sessions.find(s => s.id === id);
  }, [state.sessions]);

  return (
    <AppContext.Provider value={{ state, dispatch, getSessionById, refreshSessions }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}
