// Mock pages for testing
import React from 'react';

export const LoginPage = () => (
  <div>
    <h1>Login</h1>
    <form>
      <label htmlFor="email">Email</label>
      <input id="email" type="email" aria-label="Email" />
      <label htmlFor="password">Password</label>
      <input id="password" type="password" aria-label="Password" />
      <label>
        <input type="checkbox" aria-label="Remember Me" />
        Remember Me
      </label>
      <button type="submit">Sign In</button>
    </form>
  </div>
);

export const RegisterPage = () => (
  <div>
    <h1>Register</h1>
    <form>
      <label htmlFor="name">Full Name</label>
      <input id="name" aria-label="Full Name" />
      <label htmlFor="email">Email</label>
      <input id="email" type="email" aria-label="Email" />
      <label htmlFor="password">Password</label>
      <input id="password" type="password" aria-label="Password" />
      <label htmlFor="confirmPassword">Confirm Password</label>
      <input id="confirmPassword" type="password" aria-label="Confirm Password" />
      <button type="submit">Sign Up</button>
    </form>
  </div>
);

export const UsersPage = () => {
  const role = (window as any).mockUserRole || 'AGENCY_ADMIN';
  if (role === 'MODEL') {
    return <div>Access Denied</div>;
  }
  return (
    <div>
      <h1>Users</h1>
      <button>Add User</button>
      <table>
        <tbody>
          <tr data-testid="user-row-1">
            <td>User 1</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
};

export const ModelsPage = () => (
  <div>
    <h1>Models</h1>
    <button>Add Model</button>
    <div>model-1</div>
    <div>model-2</div>
  </div>
);

export const ChatsPage = () => (
  <div>
    <h1>Chats</h1>
  </div>
);

export const AnalyticsPage = () => (
  <div>
    <h1>Analytics</h1>
    <div>$50,000</div>
    <div>10 models</div>
  </div>
);

export const AdminDashboard = () => (
  <div>
    <h1>Admin Dashboard</h1>
  </div>
);

export const SettingsPage = () => {
  const role = (window as any).mockUserRole || 'AGENCY_ADMIN';
  return (
    <div>
      <h1>Settings</h1>
      {role !== 'MODEL' && <button>Save</button>}
    </div>
  );
};