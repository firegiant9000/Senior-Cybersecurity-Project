# Firebase Auth Emulator for LOCAL DEVELOPMENT ONLY (see docker-compose.emulator.yml).
# A "demo-" project id keeps firebase-tools fully offline from real Google Cloud.
FROM node:22-alpine@sha256:1314fb30ec37592d5845e5a160d522c0e680972aa534549940b8d73bde88481a
RUN npm install -g firebase-tools@15.36.0 && npm cache clean --force \
 && mkdir /emulator && chown node:node /emulator
WORKDIR /emulator
COPY --chown=node:node firebase.json .
USER node
EXPOSE 9099
CMD ["firebase", "emulators:start", "--only", "auth", "--project", "demo-hacker-tracker"]
