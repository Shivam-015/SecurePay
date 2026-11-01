pipeline {
    agent any

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
