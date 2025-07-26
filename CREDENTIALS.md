# AgencyDark - Login Credentials

## Test User Credentials

- **Email**: `test@example.com`
- **Password**: `password123`

## How to Login

1. Go to http://localhost:3000 in your browser
2. You'll be redirected to the login page
3. Enter the credentials above
4. Click "Sign In"

## API Test

You can also test directly via API:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

## Database Info

- **Database**: PostgreSQL (local)
- **Database Name**: `agencydark_dev`
- **Connection**: `postgresql://mariuszbudzisz@localhost:5432/agencydark_dev`

## Services Running

- **Frontend**: http://localhost:3000
- **Backend**: http://localhost:8000
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379