
from fastapi import Request
from totoms.TotoDelegateDecorator import toto_delegate
from totoms.model import ExecutionContext, UserContext


@toto_delegate
async def say_hello(request: Request, user_context: UserContext, exec_context: ExecutionContext): 
    
    return {"message": "Hello, World!"}
