# NAU Alerts
<a href="#"><img alt="Workflow status" src="https://img.shields.io/github/actions/workflow/status/naudigital/naualertsbot/docker-publish.yml"></a>
<a href="/releases"><img alt="Latest release" src="https://img.shields.io/github/v/release/naudigital/naualertsbot"></a>
<a href="/tags"><img alt="Latest tag" src="https://img.shields.io/github/v/tag/naudigital/naualertsbot"></a><br/>
<a href="#"><img alt="License" src="https://img.shields.io/github/license/naudigital/naualertsbot"/></a>
<a href="#"><img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code style: black"></a><br/>
<a href="#"><img alt="Code size" src="https://img.shields.io/github/languages/code-size/naudigital/naualertsbot"/></a>
<a href="#"><img alt="Commit activity" src="https://img.shields.io/github/commit-activity/m/naudigital/naualertsbot"/></a>
<br/>
![NAU Alerts](assets/banner.jpg)
Bot for sending notifications on NAU chats.

## Running
The example repository configuration and the docker-compose file are configured to run on the NAU Digital infrastructure. If you want to run it on your own infrastructure, you need to modify the `docker-compose.yml` and `config.yml` files.

1. Choose image and tag
```bash
export IMAGE=ghcr.io/naudigital/naualertsbot
export TAG=latest
```
2. Copy example config
```bash
cp config.example.yml config.yml
```
3. Fill `config.yml` with your data
4. Create docker config from config.yml file
```bash
docker config create naualertsbot config.yml
```
5. Deploy stack to swarm
```bash
docker stack deploy -c docker-compose.yml naualertsbot
```
