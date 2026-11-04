# Kubernetes deployment (Minikube)

The same three-service stack from `docker-compose.yml`, expressed as Kubernetes
objects. Nothing about the application changed — only *who* schedules it.

```
                NodePort 30080
                      │
                 ┌────▼─────┐
                 │  nginx   │  Deployment (1 replica) + ConfigMap
                 └────┬─────┘
                      │ http://app:5000
                 ┌────▼─────┐
                 │   app    │  Deployment (2 replicas), stateless
                 └────┬─────┘
                      │ postgres://db:5432
                 ┌────▼─────┐
                 │    db    │  Deployment (1) + PVC (ReadWriteOnce)
                 └──────────┘
```

## Why these choices

| Decision | Reason |
| --- | --- |
| `Service` named `db` and `app` | The nginx config has `proxy_pass http://app:5000`, so the Service name must match. Kubernetes DNS resolves it inside the namespace. |
| 2 app replicas | The app keeps no state; replicas can be added or removed freely. |
| `livenessProbe` → `/healthz` | Restarts the pod only if the process is genuinely dead. |
| `readinessProbe` → `/readyz` | Removes the pod from Service endpoints while the database is unreachable, without a pointless restart. |
| `strategy: Recreate` for `db` | A `ReadWriteOnce` volume cannot be mounted by two pods at once; a rolling update would deadlock. |
| `PGDATA=/var/lib/postgresql/data/pgdata` | Keeps `initdb` out of the volume root, which avoids "directory not empty" failures. |
| Secret created imperatively | Passwords never enter git, but the object still exists declaratively in the cluster. |
| `readOnlyRootFilesystem` + `emptyDir` on `/tmp` | The container cannot write to its own image; only `/tmp` is writable. |
| `drop: [ALL]` capabilities | Nothing in this stack needs elevated capabilities. |
| `imagePullPolicy: IfNotPresent` | The image is loaded into the node with `minikube image load`, so there is no registry round-trip. |

## Prerequisites

```bash
docker --version
minikube version
kubectl version --client
```

## Deploy

```bash
# 1. Build the image locally
docker build -t dockerized-webapp:1.0 .

# 2. Start the cluster (2 GB is not enough for three services + the control plane)
minikube start --driver=docker --cpus=2 --memory=3500

# 3. Load the image into the node — no registry required
minikube image load dockerized-webapp:1.0

# 4. Namespace
kubectl apply -f k8s/namespace.yaml

# 5. Database password — generated, never committed
kubectl create secret generic db-credentials -n webapp \
  --from-literal=POSTGRES_PASSWORD="$(openssl rand -hex 16)" \
  --dry-run=client -o yaml | kubectl apply -f -

# 6. Nginx config, taken from the existing file so there is one source of truth
kubectl create configmap nginx-config -n webapp \
  --from-file=default.conf=nginx/default.conf \
  --dry-run=client -o yaml | kubectl apply -f -

# 7. Everything else
kubectl apply -k k8s/
```

## Verify

```bash
kubectl get pods -n webapp -o wide
kubectl rollout status deployment/app -n webapp
kubectl get endpoints -n webapp
```

Expected: `db` becomes `1/1` first, then both `app` pods become `2/2`, then `nginx`.

## Access

```bash
minikube service nginx -n webapp --url     # prints http://192.168.49.2:30080
curl -i http://localhost:8080/             # or via: kubectl port-forward -n webapp svc/nginx 8080:80
curl -i http://localhost:8080/readyz
```

## Things worth demonstrating

```bash
# Self-healing: delete a pod, the Deployment recreates it
kubectl delete pod -n webapp -l app=app

# Horizontal scaling
kubectl scale deployment/app -n webapp --replicas=4

# Rolling update + rollback
kubectl set image deployment/app -n webapp app=dockerized-webapp:1.1
kubectl rollout status deployment/app -n webapp
kubectl rollout undo deployment/app -n webapp

# Readiness in action: stop the database, watch the app leave the endpoints
kubectl scale deployment/db -n webapp --replicas=0
kubectl get endpoints -n webapp          # app endpoints disappear
kubectl scale deployment/db -n webapp --replicas=1

# Debugging
kubectl describe pod -n webapp <pod>
kubectl logs -n webapp -l app=app --tail=50
kubectl exec -it -n webapp <pod> -- sh
```

## Tear down

```bash
kubectl delete namespace webapp     # keeps the cluster
minikube delete                     # removes the cluster entirely
```
