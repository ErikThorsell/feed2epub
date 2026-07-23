# feed2epub on Kubernetes

A portable reference (kustomize). One pod runs both containers — `server` + `fetcher` — sharing a
ReadWriteOnce `library` PVC. Adapt the image tag, the `Ingress`, and the `StorageClass` to your cluster.

```bash
cd deployment/kubernetes

# 1. Your feed list becomes the feed2epub-feeds ConfigMap (this copy is gitignored).
cp ../../feeds.example.yaml feeds.yaml   # then edit feeds.yaml

# 2. The secret feeding ${INSTAPAPER_FEED_URL} (skip if no feed references a ${VAR}).
cp secret.example.yaml secret.yaml       # then edit, and add `- secret.yaml` under resources: in kustomization.yaml

# 3. Review deployment.yaml (pin a real image tag, not :latest), pvc.yaml (storageClassName), ingress.yaml (host).
kubectl apply -k .
```

Point your OPDS reader at `http(s)://<host>/catalog.xml`.

> This is a generic starting point. The maintainer's own cluster deploys feed2epub via GitOps with a Gateway
> API `HTTPRoute`, an `ExternalSecret`, and a Longhorn PVC instead of the `Ingress`/`Secret`/default-class
> shown here — see the `manifests/feed2epub/` directory in the homelab repo.
