#!/bin/bash
# Quick verification that all Docker deployment files are in place

echo "🔍 Verifying Docker Deployment Infrastructure..."
echo ""

FILES=(
    "docker-compose.yml"
    "Dockerfile"
    "init-db.sql"
    ".env.example"
    "entrypoint.sh"
    "scripts/backup-postgres.sh"
    "scripts/restore-postgres.sh"
    "scripts/backup-postgres.bat"
    "scripts/restore-postgres.bat"
    "DOCKER_QUICKSTART.md"
    "DOCKER_DEPLOYMENT.md"
    "DOCKER_TEST.md"
    "DOCKER_INFRASTRUCTURE.md"
    "database.py"
    "db_adapter.py"
)

MISSING=0
for FILE in "${FILES[@]}"; do
    if [ -f "$FILE" ]; then
        echo "✅ $FILE"
    else
        echo "❌ MISSING: $FILE"
        ((MISSING++))
    fi
done

echo ""
if [ $MISSING -eq 0 ]; then
    echo "✅ All Docker deployment files are present!"
    echo ""
    echo "Next steps:"
    echo "1. Copy .env.example to .env"
    echo "2. Edit .env and set secure passwords"
    echo "3. Run: docker compose up -d"
    echo "4. Visit: http://localhost:5000"
    echo ""
    echo "For detailed instructions, see DOCKER_QUICKSTART.md"
else
    echo "❌ $MISSING files are missing!"
    exit 1
fi
