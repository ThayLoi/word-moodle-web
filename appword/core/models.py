from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
@dataclass
class Explanation: text: str=""; image: Optional[str]=None; table: List[Dict[str,Any]]=field(default_factory=list)
@dataclass
class OptionItem: letter: Optional[str]=None; option_text: str=""; option_image: Optional[str]=None; option_table: Optional[dict]=None
@dataclass
class Metadata: difficulty: str="medium"; tags: List[str]=field(default_factory=list); author: str="GV Huỳnh Văn Lợi"; source: Dict[str,Any]=field(default_factory=dict)
@dataclass
class Question:
    question_type: str="multichoice"; question_id: str="Q001"; question_name: str=""; question_category: str=""
    question_content: str=""; question_image: Optional[str]=None
    question_table: List[Dict[str,Any]]=field(default_factory=list); options: List[OptionItem]=field(default_factory=list)
    correct_answer: List[int]=field(default_factory=list); explanation: Explanation=field(default_factory=Explanation)
    metadata: Metadata=field(default_factory=Metadata)
