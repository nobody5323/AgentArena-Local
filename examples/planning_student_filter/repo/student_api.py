class StudentService:
    def list_students(self):
        return []


class StudentController:
    def __init__(self):
        self.service = StudentService()

    def list_students(self):
        return self.service.list_students()
