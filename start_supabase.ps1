# Wait until Docker Desktop is fully available
Write-Host "Waiting for Docker to start..."
while (-not (docker info --format "{{.ServerVersion}}" 2>$null)) {
    Start-Sleep -Seconds 5
}

Write-Host "Docker is up. Starting Supabase..."

# Navigate to your supabase project folder
Set-Location "C:\fhq-market-system"

# Start Supabase local stack
supabase start
