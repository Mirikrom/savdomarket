export const LOCAL_DEBTOR_PREFIX = 'local:'

export function isLocalDebtorRef(value) {
  return typeof value === 'string' && value.startsWith(LOCAL_DEBTOR_PREFIX)
}

export function localDebtorRef(clientUuid) {
  return `${LOCAL_DEBTOR_PREFIX}${clientUuid}`
}
