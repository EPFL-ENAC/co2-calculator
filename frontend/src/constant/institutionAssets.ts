// Files of the institution folder that the deployment mounts and nginx
// serves at /institution/ (#3244). docker/institution.sh refuses to start
// the container when one is missing.
export const INSTITUTION_LOGO_URL = '/institution/logo.svg';
