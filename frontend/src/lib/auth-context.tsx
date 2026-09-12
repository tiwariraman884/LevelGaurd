'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { UserRole } from '@/lib/types';
import { ApiClient, getStoredToken, setStoredToken } from '@/lib/api-client';

export interface AuthUser {
  id?: number;
  email: string;
  fullName: string;
  role: UserRole;
  backendRole: string;
  designation?: string;
  department?: string;
  district?: string;
  state?: string;
  companyName?: string;
  gstNumber?: string;
  lutNumber?: string;
}

interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string, selectedRole?: UserRole) => Promise<AuthUser>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => void;
}

export interface RegisterData {
  email: string;
  password: string;
  fullName: string;
  role: UserRole;
  designation?: string;
  department?: string;
  district?: string;
  state?: string;
  companyName?: string;
  gstNumber?: string;
  lutNumber?: string;
  entityType?: string;
  entityCategory?: string;
  address?: string;
  badgeNumber?: string;
  organization?: string;
}

const AUTH_STORAGE_KEY = 'labelguard_auth_user';

export function mapBackendRoleToFrontend(backendRole: string): UserRole {
  switch (backendRole?.toLowerCase()) {
    case 'district_collector':
      return 'controller';
    case 'state_admin':
    case 'national_admin':
    case 'admin':
      return 'admin';
    case 'inspector':
      return 'inspector';
    case 'auditor':
      return 'auditor';
    default:
      return 'inspector';
  }
}

export function getDefaultRoute(roleOrBackendRole: string): string {
  switch (roleOrBackendRole?.toLowerCase()) {
    case 'vendor':
      return '/vendor/dashboard';
    case 'inspector':
      return '/inspector/scans';
    case 'controller':
    case 'district_collector':
      return '/dashboard/district';
    case 'admin':
    case 'state_admin':
    case 'national_admin':
      return '/dashboard/admin';
    case 'auditor':
      return '/search';
    default:
      return '/inspector/scans';
  }
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Restore session from real backend using stored JWT token
  useEffect(() => {
    async function restoreSession() {
      const token = getStoredToken();
      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        const backendUser = await ApiClient.getCurrentUser();
        const frontendRole = mapBackendRoleToFrontend(backendUser.role);
        const authUser: AuthUser = {
          id: backendUser.id,
          email: backendUser.email,
          fullName: backendUser.full_name || 'Authorized Officer',
          role: frontendRole,
          backendRole: backendUser.role,
          designation: getDesignationForRole(backendUser.role),
        };
        setUser(authUser);
        localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(authUser));
      } catch {
        // Token is invalid or expired
        setStoredToken(null);
        localStorage.removeItem(AUTH_STORAGE_KEY);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    }

    restoreSession();
  }, []);

  const login = useCallback(async (email: string, password: string, selectedRole?: UserRole): Promise<AuthUser> => {
    void selectedRole;
    // Authenticate with real FastAPI backend
    await ApiClient.login(email, password);

    // Fetch authoritative user details from /api/v1/auth/me
    const backendUser = await ApiClient.getCurrentUser();
    const frontendRole = mapBackendRoleToFrontend(backendUser.role);

    const authUser: AuthUser = {
      id: backendUser.id,
      email: backendUser.email,
      fullName: backendUser.full_name || 'Legal Metrology Officer',
      role: frontendRole,
      backendRole: backendUser.role,
      designation: getDesignationForRole(backendUser.role),
    };

    setUser(authUser);
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(authUser));
    return authUser;
  }, []);

  const register = useCallback(async (data: RegisterData) => {
    // For registration
    await new Promise((resolve) => setTimeout(resolve, 600));
    const authUser: AuthUser = {
      email: data.email,
      fullName: data.fullName,
      role: data.role,
      backendRole: data.role,
      designation: data.designation,
      department: data.department,
      district: data.district,
      state: data.state,
      companyName: data.companyName,
      gstNumber: data.gstNumber,
      lutNumber: data.lutNumber,
    };

    setUser(authUser);
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(authUser));
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    ApiClient.logout();
    localStorage.removeItem(AUTH_STORAGE_KEY);
    if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

function getDesignationForRole(backendRole: string): string {
  switch (backendRole?.toLowerCase()) {
    case 'inspector':
      return 'Legal Metrology Inspector';
    case 'district_collector':
      return 'District Collector / Controller';
    case 'state_admin':
      return 'State Enforcement Director';
    case 'national_admin':
    case 'admin':
      return 'National Legal Metrology Director';
    case 'auditor':
      return 'Compliance Audit Observer';
    default:
      return 'Authorized Officer';
  }
}
