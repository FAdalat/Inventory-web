import json 
import os 

try :
    import anthropic 
except ImportError :
    anthropic =None 

AI_MODEL ="claude-haiku-4-5-20251001"

MAX_BULLETS_PER_SECTION =5 

SYSTEM_PROMPT ="""You are a business analyst for a small wholesale fashion shop's owner.

You will be given a JSON summary of one month's sales data: revenue, profit, \
discounts given, top and slow-moving products, and staff performance. All \
monetary figures in that data are in US dollars.

Call the submit_monthly_insight tool with your analysis. Rules:
- All monetary figures you write must use the $ symbol (e.g. $1,234.56).
  Never use £, €, or any other currency symbol or code.
- Every bullet must be under 20 words.
- Reference actual numbers and product names from the data provided.
- Do not invent figures that aren't in the data.
- If a product sells well but has thin or negative margin, say so explicitly
  under "warnings" — that pattern matters more than raw sales volume.
- If there isn't enough data to say something meaningful for a section,
  return an empty list for it rather than making something up."""

INSIGHT_TOOL ={
"name":"submit_monthly_insight",
"description":"Submit the structured monthly business insight report.",
"input_schema":{
"type":"object",
"properties":{
"summary":{
"type":"string",
"description":"2-3 sentence plain-language overview of how the month went",
},
"top_products":{
"type":"array",
"items":{"type":"string"},
"description":"Short bullets on best-selling products, each under 20 words",
},
"slow_products":{
"type":"array",
"items":{"type":"string"},
"description":"Short bullets on slow-moving products, each under 20 words",
},
"recommendations":{
"type":"array",
"items":{"type":"string"},
"description":"Short, concrete, actionable bullets",
},
"warnings":{
"type":"array",
"items":{"type":"string"},
"description":"Bullets flagging real risk (e.g. thin margins); empty if none",
},
},
"required":["summary","top_products","slow_products","recommendations","warnings"],
},
}


class AIInsightsUnavailable (Exception ):
    """Raised whenever the AI feature can't produce a result — missing
    package, missing API key, a failed request, or a malformed response.
    Callers catch this and show a friendly message instead of a 500."""


def is_configured ()->bool :
    """Whether the AI feature can run at all in this environment. Used to
    decide whether to show a 'Generate' button or a setup hint instead."""
    return anthropic is not None and bool (os .environ .get ("ANTHROPIC_API_KEY"))


def generate_monthly_insight (stats :dict )->dict :
    """
    stats is the dict produced by build_monthly_stats() in app.py — plain
    numbers and short lists, already aggregated in Python rather than
    handed to the model as raw database rows. Returns a dict matching
    INSIGHT_TOOL's schema above. Raises AIInsightsUnavailable on any
    failure (missing key, network error, no tool call back) so the
    caller never has to deal with an unhandled exception type from this
    module.
    """
    if anthropic is None :
        raise AIInsightsUnavailable (
        "The 'anthropic' package isn't installed. Run: pip install anthropic"
        )

    api_key =os .environ .get ("ANTHROPIC_API_KEY")
    if not api_key :
        raise AIInsightsUnavailable (
        "ANTHROPIC_API_KEY is not set. Add it to a .env file (see .env.example)."
        )

    client =anthropic .Anthropic (api_key =api_key )

    try :
        response =client .messages .create (
        model =AI_MODEL ,
        max_tokens =1024 ,
        system =SYSTEM_PROMPT ,
        tools =[INSIGHT_TOOL ],
        tool_choice ={"type":"tool","name":"submit_monthly_insight"},
        messages =[{"role":"user","content":json .dumps (stats )}],
        )
    except Exception as exc :
        raise AIInsightsUnavailable (f"The AI request failed: {exc }")from exc 

    tool_use_block =next (
    (block for block in response .content if getattr (block ,"type",None )=="tool_use"),
    None ,
    )
    if tool_use_block is None :
        raise AIInsightsUnavailable (
        "The AI didn't return a structured response — try regenerating."
        )

    parsed =tool_use_block .input 

    def _bullets (key :str )->list [str ]:
        items =parsed .get (key ,[])
        if not isinstance (items ,list ):
            return []
        return [str (item )for item in items ][:MAX_BULLETS_PER_SECTION ]

    return {
    "summary":str (parsed .get ("summary",""))[:1000 ],
    "top_products":_bullets ("top_products"),
    "slow_products":_bullets ("slow_products"),
    "recommendations":_bullets ("recommendations"),
    "warnings":_bullets ("warnings"),
    }
