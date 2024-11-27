# Run in a container

Pre-built containers with dls-pmac-lib and its dependencies already
installed are available on [Github Container Registry](https://ghcr.io/DiamondLightSource/dls-pmac-lib).

## Starting the container

To pull the container from github container registry and run:

```
$ docker run ghcr.io/diamondlightsource/dls-pmac-lib:latest --version
```

To get a released version, use a numbered release instead of `latest`.
