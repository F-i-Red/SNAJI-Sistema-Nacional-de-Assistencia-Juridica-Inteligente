
class ContextMemory:

    def __init__(self):
        self.memory = {}

    def store(self, case_id, context):

        self.memory[case_id] = context

    def retrieve(self, case_id):

        return self.memory.get(case_id, {})
