from pydantic import BaseModel

class UpdateResponse(BaseModel):
  """
  Response for successful operations
  """
  success: bool
  message: str

