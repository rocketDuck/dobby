FROM python:3.8-slim as builder
COPY dist /dist
RUN pip install --root /build /dist/dobby-*.whl

FROM python:3.8-slim
COPY --from=builder /build /
CMD [ "bash" ]
