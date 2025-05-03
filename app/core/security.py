from passlib.context import CryptContext

# 创建密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """
    生成密码哈希
    
    Args:
        password: 原始密码
        
    Returns:
        密码哈希
    """
    return pwd_context.hash(password)
