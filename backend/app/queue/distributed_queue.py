
class DistributedQueue:

    def enqueue(self, task):

        return {
            "queued": True,
            "task": task
        }

    def dequeue(self):

        return {
            "task": None
        }
