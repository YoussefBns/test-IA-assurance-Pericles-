param(
    [string]$RepositoryUrl = "https://github.com/imsxm-perso/testyouseff.git"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git doit être installé." }
if (Test-Path ".git") { throw "Un dépôt local existe déjà. Aucune modification : utiliser votre workflow Git habituel." }
$name = git config user.name
$email = git config user.email
if (-not $name -or -not $email) { throw "Configurer personnellement user.name et user.email dans Git avant de continuer." }
$remote = git ls-remote $RepositoryUrl
if ($LASTEXITCODE -ne 0) { throw "Dépôt distant inaccessible. Vérifier le nom et les autorisations ; aucun dépôt local créé." }
if ($remote) { throw "Le dépôt distant n'est pas vide. Aucune publication pour éviter d'écraser ou de créer un historique divergent." }
Write-Host "Les données du test seront incluses. Utiliser uniquement le dépôt privé autorisé."
$answer = Read-Host "Confirmer la publication dans $RepositoryUrl (taper PUBLIER)"
if ($answer -cne "PUBLIER") { throw "Publication annulée." }
git init -b livraison-test-ia
if ($LASTEXITCODE -ne 0) { throw "Échec git init." }
git add .
if ($LASTEXITCODE -ne 0) { throw "Échec git add." }
git commit -m "feat: assurance churn, RAG and FastAPI technical test"
if ($LASTEXITCODE -ne 0) { throw "Échec du commit ; rien n'a été poussé." }
git remote add origin $RepositoryUrl
if ($LASTEXITCODE -ne 0) { throw "Échec de configuration origin." }
git push -u origin livraison-test-ia
if ($LASTEXITCODE -ne 0) { throw "Échec du push ; conserver le dossier et examiner le message Git." }
Write-Host "Branche livraison-test-ia publiée. Aucun force-push effectué."
