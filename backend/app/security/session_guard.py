
class SessionGuard:

    MAX_REQUESTS_PER_MINUTE = 60

    def validate_rate_limit(self, requests):

        return requests < self.MAX_REQUESTS_PER_MINUTE
