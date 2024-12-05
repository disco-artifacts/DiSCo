class StackHandlingException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        
class StackSizeOverflow(StackHandlingException):
    pass