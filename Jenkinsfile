pipeline {
    agent any

    environment {
        KIND_CLUSTER_NAME = 'securepay'
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 30, unit: 'MINUTES')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('PostgreSQL checks and tests') {
            steps {
                sh 'docker compose -f docker-compose.ci.yml up --build --abort-on-container-exit --exit-code-from tests tests'
            }
        }

        stage('Build application image') {
            steps {
                sh "docker build --tag securepay:${env.BUILD_NUMBER} ."
            }
        }

        stage('Deploy to local kind') {
            steps {
                sh '''
                    set -eu
                    APP_IMAGE="securepay:${BUILD_NUMBER}"
                    kind get clusters | grep -Fx "$KIND_CLUSTER_NAME" >/dev/null || {
                        echo "Required kind cluster '$KIND_CLUSTER_NAME' does not exist." >&2
                        exit 1
                    }
                    kubectl config use-context "kind-${KIND_CLUSTER_NAME}"
                    test "$(kubectl config current-context)" = "kind-${KIND_CLUSTER_NAME}"
                    docker image inspect "$APP_IMAGE" >/dev/null
                    kind load docker-image "$APP_IMAGE" --name "$KIND_CLUSTER_NAME"

                    kubectl apply -f k8s/namespace.yaml
                    if ! kubectl -n securepay get secret securepay-secrets >/dev/null 2>&1; then
                        echo 'Kubernetes Secret securepay-secrets is missing in namespace securepay.' >&2
                        echo 'Create it once using the README local Kubernetes instructions, then rerun this build.' >&2
                        exit 1
                    fi

                    kubectl apply -f k8s/configmap.yaml
                    kubectl apply -f k8s/postgres.yaml
                    kubectl apply -f k8s/redis.yaml
                    kubectl -n securepay rollout status statefulset/securepay-db --timeout=300s
                    kubectl -n securepay rollout status deployment/securepay-redis --timeout=180s

                    kubectl -n securepay delete job securepay-migrate --ignore-not-found=true
                    sed "s|securepay:dev|${APP_IMAGE}|g" k8s/migration-job.yaml | kubectl apply -f -
                    kubectl -n securepay wait --for=condition=complete job/securepay-migrate --timeout=300s

                    sed "s|securepay:dev|${APP_IMAGE}|g" k8s/app.yaml | kubectl apply -f -
                    kubectl -n securepay rollout status deployment/securepay-web --timeout=240s
                    kubectl -n securepay rollout status deployment/securepay-worker --timeout=180s
                    kubectl -n securepay rollout status deployment/securepay-beat --timeout=180s
                '''
            }
        }
    }

    post {
        always {
            script {
                sh(
                    script: 'docker compose -f docker-compose.ci.yml down --remove-orphans',
                    returnStatus: true
                )
            }
        }
    }
}
