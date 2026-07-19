# GitHub Actions Workload Identity Federation

* Workload Identity (OIDC) 連携を使って認証する設定です。
* GitHub Action による自動デプロイのためには、以下を事前に準備する必要があります。

## Variables

* "your-..." 及び、その他推奨設定例の値も適宜調整してご利用ください。

```bash
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

POOL_NAME="github-pool"
PROVIDER_NAME="github-provider"
SA_NAME="github-actions-deployer"
# service account の識別子 (メールを受信できるわけではない)
WIF_SERVICE_ACCOUNT="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# GitHub repository
GITHUB_REPO_OWNER="your-github-username-or-org"
GITHUB_REPO_NAME="your-repo-name"
GITHUB_REPO="${GITHUB_REPO_OWNER}/${GITHUB_REPO_NAME}"

# GCP Artifact Registry
REGION=us-central1
# Google Artifact Registry の cloud run デフォルトのリポジトリ名
GAR_REPO_NAME=cloud-run-source-deploy
GAR_REPO_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${GAR_REPO_NAME}"
```

## Setup GCP Service Account

```bash
# 専用サービスアカウントの作成 (権限設定は後述)
gcloud iam service-accounts create $SA_NAME \
    --project="$PROJECT_ID" \
    --display-name="GitHub Actions Deployer"

# 一覧
gcloud iam service-accounts list
# WIF_SERVICE_ACCOUNT の値が表示されるはず
```

* service account に対して必要なGCP権限を別途付与する
* 実際に動かしてエラーログから特定するのが簡単

```bash
# 「Artifact Registryの書き込み権限」は、通常はプロジェクトに対して設定する
# Artifact Registry に Docker イメージをプッシュ
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${WIF_SERVICE_ACCOUNT}" \
    --role="roles/artifactregistry.writer"

# 【参考】特定のリポジトリ単体に権限を絞り込む場合
gcloud artifacts repositories add-iam-policy-binding $GAR_REPO_NAME \
    --location=$REGION \
    --project=$PROJECT_ID \
    --member="serviceAccount:${WIF_SERVICE_ACCOUNT}" \
    --role="roles/artifactregistry.writer"

# 「Cloud Run 開発者権限」は、プロジェクトに対して設定する
# (Cloud Run のサービスを新しく作ったり、既存のものを更新・デプロイしたりする権限)
# (注) 事前に一度も gcloud で手動デプロイしていない場合は初回のみ roles/run.admin が必要とのこと
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${WIF_SERVICE_ACCOUNT}" \
    --role="roles/run.developer"

# 「特定のサービスアカウントを操作する権限」を追加する
# projects 全体ではなく、service-accounts に対して権限を追加する (最小特権の原則)
# Compute EngineのデフォルトSA（Cloud Runの実行元）を指定するのが一般的
RUN_IMAGE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# GitHub Actionsが「身代わりとしてアタッチしたいSA」のIDをピンポイントで指定する
gcloud iam service-accounts add-iam-policy-binding $RUN_IMAGE_SA \
    --project=$PROJECT_ID \
    --member="serviceAccount:${WIF_SERVICE_ACCOUNT}" \
    --role="roles/iam.serviceAccountUser"
```

* 権限の確認コマンド

```bash
# 【参考】特定のリポジトリ単体に権限を絞り込む場合
gcloud artifacts repositories get-iam-policy $GAR_REPO_NAME \
    --location=$REGION \
    --project=$PROJECT_ID \
    --flatten="bindings[].members" \
    --format="table(bindings.members, bindings.role)"

# projects get-iam-policy 一覧
gcloud projects get-iam-policy $PROJECT_ID \
    --flatten="bindings[].members" \
    --format="table(bindings.members, bindings.role)" \
    --sort-by="bindings.members"

gcloud iam service-accounts get-iam-policy $RUN_IMAGE_SA \
    --project=$PROJECT_ID \
    --flatten="bindings[].members" \
    --format="table(bindings.members, bindings.role)"
```

* 実行用 service account にも別途権限付与が必要とのこと

```bash
RUN_IMAGE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# まずは secrets 一覧
gcloud secrets list --project="$PROJECT_ID" --format="value(name)"

# 現状の確認用コマンド (LINE_CHANNEL_ACCESS_TOKEN も同様)
gcloud secrets get-iam-policy LINE_CHANNEL_SECRET \
    --project=$PROJECT_ID \
    --flatten="bindings[].members" \
    --format="table(bindings.members, bindings.role)" \
    --sort-by="bindings.members"

# もし権限なければ、個別に許可する場合のコマンド (LINE_CHANNEL_ACCESS_TOKEN も同様)
gcloud secrets add-iam-policy-binding LINE_CHANNEL_SECRET \
    --project="$PROJECT_ID" \
    --member="serviceAccount:${RUN_IMAGE_SA}" \
    --role="roles/secretmanager.secretAccessor"

# または、project 全体に対して許可するコマンド
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${RUN_IMAGE_SA}" \
    --role="roles/secretmanager.secretAccessor"
```

## Setup GCP Workload Identity Pool/Provider

```bash
# Workload Identity プールの作成 (外部 ID（GitHubなど）を管理するためのプール)
gcloud iam workload-identity-pools create $POOL_NAME \
    --project="$PROJECT_ID" \
    --location="global" \
    --display-name="GitHub Actions Pool"

# Workload Identity プロバイダの作成 (GitHub OIDCトークンを検証するためのプロバイダ)
gcloud iam workload-identity-pools providers create-oidc $PROVIDER_NAME \
    --project="$PROJECT_ID" \
    --location="global" \
    --workload-identity-pool="$POOL_NAME" \
    --display-name="GitHub Actions Provider" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --attribute-condition="attribute.repository=='${GITHUB_REPO}'"

# (参考) 以下を追加すると実行者の制限も可能とのこと
# --attribute-mapping に ,attribute.actor=assertion.actor
# --attribute-condition に && attribute.actor == 'github-username'

# 一覧
gcloud iam workload-identity-pools list --location="global"
gcloud iam workload-identity-pools providers list \
  --location="global" --workload-identity-pool=$POOL_NAME

# 作成した $POOL_NAME のIDを変数に設定
WORKLOAD_IDENTITY_POOL_ID=$(gcloud iam workload-identity-pools describe $POOL_NAME \
  --project="${PROJECT_ID}" \
  --location="global" \
  --format="value(name)")
```

```bash
# 特定のGitHubリポジトリからのみアクセスを許可（IAMポリシーバインディング）
# (注) "roles/iam.serviceAccountTokenCreator" が必要という説は誤りとのこと
gcloud iam service-accounts add-iam-policy-binding $WIF_SERVICE_ACCOUNT \
    --project="$PROJECT_ID" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/${WORKLOAD_IDENTITY_POOL_ID}/attribute.repository/${GITHUB_REPO}"

# 確認
gcloud iam service-accounts get-iam-policy $WIF_SERVICE_ACCOUNT

# 設定完了後、GitHub Actions側に記述する 「プロバイダ番号」 を確認
gcloud iam workload-identity-pools providers describe $PROVIDER_NAME \
    --project="$PROJECT_ID" \
    --location="global" \
    --workload-identity-pool="$POOL_NAME" \
    --format="value(name)"

# 出力例
# projects/123456789012/locations/global/workloadIdentityPools/github-pool/providers/github-provider

WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/providers/${PROVIDER_NAME}"
```

## Setup GitHub

```bash
# ログイン状態の確認
gh auth status

gh secret set PROJECT_ID --body $PROJECT_ID
gh secret set WIF_PROVIDER --body $WIF_PROVIDER
gh secret set WIF_SERVICE_ACCOUNT --body $WIF_SERVICE_ACCOUNT
gh secret set GAR_REPO_URL --body $GAR_REPO_URL

# 一覧
gh secret list
```

## GCP Artifact Registry

* 操作コマンドのメモ

```bash
PACKAGE_NAME=$GITHUB_REPO_NAME

# tag 以外も含めて全ての image を一覧
gcloud artifacts docker images list $GAR_REPO_URL --include-tags
gcloud artifacts docker images list "${GAR_REPO_URL}/${PACKAGE_NAME}" --include-tags

# tag を一覧
gcloud artifacts docker tags list $GAR_REPO_URL
gcloud artifacts docker tags list "${GAR_REPO_URL}/${PACKAGE_NAME}"

# (参考) docker image 以外も含めて一覧 (docker image のサイズは出力されない)
gcloud artifacts versions list \
    --project="$PROJECT_ID" \
    --repository="$GAR_REPO_NAME" \
    --location="$REGION" \
    --package="$PACKAGE_NAME"

# (参考) registry 内のファイル一覧
gcloud artifacts files list \
    --project="$PROJECT_ID" \
    --repository="$GAR_REPO_NAME" \
    --location="$REGION" \
    --package=$PACKAGE_NAME
```

* 不要な image の削除

```bash
# 利用量合計の確認
gcloud artifacts repositories describe $GAR_REPO_NAME \
    --project=$PROJECT_ID \
    --location=$REGION \
    --format="value(sizeBytes.size())"

# latest 以外を削除する
IMAGE_LIST=($(gcloud artifacts docker images list $GAR_REPO_URL \
    --include-tags \
    --filter="NOT tags:latest" \
    --format="value(format('{0}@{1}', package, version))"))

# Mac zsh 用のループ
for IMAGE in $IMAGE_LIST; do
    gcloud artifacts docker images delete "$IMAGE" --delete-tags --quiet
done
```

* cleanup policy の設定

```bash
# 一覧
gcloud artifacts repositories list-cleanup-policies $GAR_REPO_NAME \
    --project=$PROJECT_ID \
    --location=$REGION

# 例: latest だけを残して、それ以外のタグが外れたゴミ（UNTAGGED）だけを対象にする
# pushされてから24時間（86400秒）経ったゴミを消す
gcloud artifacts repositories set-cleanup-policies $GAR_REPO_NAME \
    --project=$PROJECT_ID \
    --location=$REGION \
    --policy=.gar_policy.json
```
