# Inventory Management Application

A complete, production-ready inventory management system with multi-shop support, stock transfers, user management, and database backup/restore functionality.

## Features

### Inventory Management
- **Product Management**: Add, edit, and delete products
- **Shop Management**: Create and manage multiple shop locations
- **Stock Tracking**: Track inventory across multiple shops with support for different product cuts/types
- **Stock Transfer**: Transfer inventory between shops with quantity validation
- **Price Tracking**: Store and display product prices
- **Search & Filter**: Search products and filter by shop location

### User Management
- **Authentication**: Secure login/logout with session management
- **Role-Based Access Control (RBAC)**: Admin and normal user roles
- **User Management**: Create, edit, and deactivate users (admin only)
- **Authorization**: Role-based access to features and API endpoints

### Database Management
- **Backup/Export**: Export complete database to portable JSON format
- **Restore**: Restore database from backups (admin only)
- **User Data Preservation**: Users, roles, and permissions are preserved during backup/restore
- **Password Hashing**: Secure password storage with bcrypt hashing

### Deployment
- **Docker Support**: Complete Docker and Docker Compose configuration
- **PostgreSQL Database**: Production-grade database backend
- **Persistent Volumes**: Database data persists across container restarts
- **Health Checks**: Built-in health checks for all services
- **Environment Configuration**: Flexible configuration through environment variables

## Requirements

- **Docker**: 20.10 or higher
- **Docker Compose**: 1.29 or higher

No additional software is required on the server; everything runs in containers.

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/ovidiumihailpascal/inventory.git
cd inventory
```

### 2. Configure Environment Variables

Copy the example configuration file:

```bash
cp .env.example .env
```

Edit `.env` and update the following values for your environment:

```env
# Required: Change these to secure values for production
DB_PASSWORD=<secure-database-password>
FLASK_SECRET=<secure-random-secret-key>
INVENTORY_PASS=<new-admin-password>
POSTGRES_ADMIN_PASSWORD=<postgres-admin-password>

# Optional: Customize other settings
DB_HOST=postgres                    # Docker service name (usually no change needed)
DB_PORT=5432                        # PostgreSQL port
DB_NAME=inventory                   # Database name
DB_USER=inventory_app               # Database user
APP_PORT=5000                       # Application port on host
FLASK_ENV=production                # Set to 'development' for debugging
```

**Important Security Notes:**
- Never commit `.env` to version control
- Use strong, random passwords for production
- Change all default credentials before deploying to production
- The application will run with default test credentials if `.env` is not configured, but this should never be used in production

### 3. Start the Application

```bash
docker compose up -d
```

The application will:
1. Create and initialize the PostgreSQL database
2. Run database migrations
3. Create a default admin user (or skip if users already exist)
4. Start the Flask application with Gunicorn

### 4. Access the Application

Open your browser and navigate to:

```
http://localhost:5000
```

Default credentials (if not changed in `.env`):
- **Username**: `admin`
- **Password**: `admin` (or the value set in `INVENTORY_PASS`)

**⚠️ Change the default password immediately in production!**

## Configuration

### Environment Variables

All configuration is done through environment variables in the `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `postgres` | PostgreSQL hostname (use service name in Docker) |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `inventory` | Database name |
| `DB_USER` | `inventory_app` | Database user |
| `DB_PASSWORD` | - | Database password (**required**, must be set) |
| `FLASK_SECRET` | - | Flask session secret key (**required** for production) |
| `FLASK_ENV` | `production` | Flask environment (`production` or `development`) |
| `INVENTORY_USER` | `admin` | Default admin username |
| `INVENTORY_PASS` | `admin` | Default admin password |
| `APP_PORT` | `5000` | Application port on the host |
| `POSTGRES_ADMIN_USER` | `postgres` | PostgreSQL admin user |
| `POSTGRES_ADMIN_PASSWORD` | - | PostgreSQL admin password |

### Docker Compose

The `docker-compose.yml` file defines:

- **inventory-app**: Flask application with Gunicorn
- **postgres**: PostgreSQL database
- **inventory_network**: Internal Docker network for service communication
- **inventory_postgres_data**: Persistent volume for database storage

Database data is stored in a named volume (`inventory_postgres_data`) and will persist even if containers are stopped or removed.

## Usage

### Logging In

1. Navigate to `http://localhost:5000`
2. Enter your username and password
3. Click "Login"

### Managing Inventory

1. Go to **Inventory** to view all products
2. Use **Search** to find specific products
3. Use **Filter by Shop** to view stock at specific locations
4. Click **Add** to create new products
5. Click **Edit** to change quantities
6. Click **Transfer** to move stock between shops
7. Click **Delete** to remove items

### Managing Shops

1. Go to **Shops** to view all shop locations
2. Click **Add Shop** to create a new location
3. Click **Delete** to remove a shop (only if no inventory exists)

### Managing Users

1. Go to **User Management** (admin only)
2. View all users and their roles
3. Click **Create User** to add new users
4. Click **Edit** to change user details
5. Click **Deactivate** to disable accounts

### Backup & Restore

1. Go to **Backup & Restore**
2. Click **Export Database** to download a backup JSON file
3. Click **Choose File** and select a previously downloaded backup to restore
4. Click **Restore Database** to import the backup

**Important:**
- Only admin users can export/restore
- Backups include all data (users, products, inventory)
- Restore will replace the entire database with the backup data
- Keep regular backups stored safely

## Database

### Initialization

The database is automatically initialized when the containers start:

1. `init-db.sql` creates the initial schema
2. Application creates default tables if they don't exist
3. Default admin user is created on first run

### Migrations

The application uses simple schema validation to ensure all required tables and columns exist. If you update the application:

1. Stop the containers: `docker compose down`
2. Pull the latest code: `git pull`
3. Start the containers again: `docker compose up -d`
4. The application will automatically apply any necessary schema updates

### Data Persistence

Database data is stored in a Docker named volume:

```bash
# View all volumes
docker volume ls | grep inventory

# Inspect volume details
docker volume inspect inventory_postgres_data

# The data persists at: /var/lib/docker/volumes/inventory_postgres_data/_data
```

To preserve data during updates:

```bash
# Stop and remove containers (but keep the volume)
docker compose down

# Pull updates
git pull

# Restart with the same volume (data persists)
docker compose up -d
```

To completely reset the database (destructive):

```bash
# Stop containers and remove the volume
docker compose down -v

# This deletes all data!
docker volume rm inventory_postgres_data

# Restart to create a fresh database
docker compose up -d
```

## Running & Deployment

### Start the Application

```bash
# Start in background
docker compose up -d

# View logs
docker compose logs -f inventory-app

# View database logs
docker compose logs -f postgres
```

### Stop the Application

```bash
# Stop all containers (keeps data)
docker compose down

# Stop and remove all data (destructive)
docker compose down -v
```

### Update the Application

```bash
# Pull the latest code
git pull

# Restart containers to use updated code
docker compose up -d
```

### Health Check

```bash
# Check application health
curl http://localhost:5000/

# Check database connection
docker compose exec postgres pg_isready -U inventory_app -d inventory
```

## Troubleshooting

### Application won't start

1. Check logs: `docker compose logs inventory-app`
2. Verify `.env` file exists and is properly configured
3. Verify `.env` has all required variables (see Configuration section)
4. Ensure port 5000 is not in use: `netstat -an | find "5000"`

### Database connection error

1. Check PostgreSQL logs: `docker compose logs postgres`
2. Verify `DB_HOST=postgres` (not localhost) in `.env`
3. Verify database credentials in `.env`
4. Check if database container is running: `docker compose ps`

### Database seems corrupted

1. Stop the application: `docker compose down`
2. Restore from a backup: `docker compose up -d` then use Backup & Restore feature
3. If no backup available, reset the database (destructive):
   ```bash
   docker compose down -v
   docker compose up -d
   ```

### Container won't stop cleanly

```bash
# Force stop containers
docker compose kill

# Remove stopped containers
docker compose rm -f
```

## Development

### Running in Development Mode

In `.env`, set:

```env
FLASK_ENV=development
```

Then restart:

```bash
docker compose up -d
```

This enables Flask debugging and auto-reloading on code changes.

### Running the Flask Application Locally (Without Docker)

If you need to run outside Docker for development:

```bash
# Install dependencies
pip install -r requirements.txt

# Set up database URL
export DB_HOST=localhost  # Or your PostgreSQL host
export DB_PORT=5432
export DB_NAME=inventory
export DB_USER=inventory_app
export DB_PASSWORD=your_password
export FLASK_SECRET=your_secret

# Run Flask
python app.py
```

## Architecture

### Components

- **Frontend**: HTML/CSS/JavaScript (Bootstrap 5 for UI)
- **Backend**: Python Flask application
- **Database**: PostgreSQL with persistent Docker volume
- **Web Server**: Gunicorn (production WSGI server)
- **Container Runtime**: Docker and Docker Compose

### File Structure

```
inventory/
├── app.py                  # Main Flask application
├── Dockerfile              # Docker image configuration
├── docker-compose.yml      # Docker Compose configuration
├── entrypoint.sh           # Container startup script
├── init-db.sql             # Database schema initialization
├── requirements.txt        # Python dependencies
├── .env.example            # Example environment variables
├── .gitignore              # Git ignore rules
├── README.md               # This file
│
├── templates/              # HTML templates
│   ├── index.html          # Main inventory page
│   ├── login.html          # Login page
│   ├── ...
│
├── static/                 # Static assets (CSS, JS, images)
│   ├── css/
│   ├── js/
│   └── ...
│
└── scripts/                # Utility scripts
```

## Security

### Authentication & Authorization

- Passwords are hashed using bcrypt (never stored in plaintext)
- Sessions are stored server-side
- All protected endpoints require login
- Admin-only endpoints are enforced server-side (not just hidden in UI)
- CSRF protection is implemented on form submissions

### Database Security

- Database connections use credentials from environment variables
- No SQL injection vulnerabilities (all queries use parameterized statements)
- Foreign key constraints maintain data integrity
- Backup/restore functionality is restricted to admin users

### Deployment Security

- Default credentials must be changed in production
- Flask secret key must be set to a random value
- Database password must be strong
- Use HTTPS in production (configure reverse proxy/load balancer)
- Regularly update Docker images: `docker compose pull && docker compose up -d`

## API Reference

### Inventory Endpoints

- `GET /api/items` - List all inventory items
- `POST /api/items` - Add a new item
- `PUT /api/items/<id>` - Update item quantity
- `DELETE /api/items/<id>` - Delete an item
- `POST /api/transfer` - Transfer stock between shops

### Shop Endpoints

- `GET /api/shops` - List all shops
- `POST /api/shops` - Create a new shop
- `DELETE /api/shops/<id>` - Delete a shop

### Product Lists (Planned Features)

- `GET /api/lists` - List all product lists
- `POST /api/lists` - Create a new list
- `GET /api/lists/<id>` - Get list items

### User Management (Admin Only)

- `GET /api/users` - List all users
- `POST /api/users` - Create a new user
- `PUT /api/users/<id>` - Update user
- `DELETE /api/users/<id>` - Deactivate user

## Contributing

To contribute improvements:

1. Clone the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Test thoroughly (especially with Docker)
5. Create a pull request with a clear description

## License

[Add your license here if applicable]

## Support

For issues, feature requests, or questions:

1. Check the Troubleshooting section above
2. Review existing documentation files in the repository
3. Open an issue on GitHub with:
   - A clear description of the problem
   - Steps to reproduce
   - Expected vs actual behavior
   - Relevant error messages or logs

## Changelog

### Version 1.0.0 (Initial Release)

#### Features
- ✅ Complete inventory management system
- ✅ Multi-shop support with stock transfer
- ✅ User management with role-based access control
- ✅ Database backup and restore functionality
- ✅ Docker deployment with persistent storage
- ✅ Secure authentication and authorization
- ✅ Product search and filtering

#### Fixes & Improvements
- ✅ Fixed logout functionality
- ✅ Fixed database restore (users and data fully restored)
- ✅ Fixed stock transfer between shops
- ✅ Fixed product list loading
- ✅ Comprehensive error handling and validation
- ✅ Production-ready Docker configuration

---

**Last Updated**: 2026-09-01  
**Repository**: https://github.com/ovidiumihailpascal/inventory
