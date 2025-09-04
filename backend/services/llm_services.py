import os
import logging
from groq import Groq

# Set up logger
logger = logging.getLogger("llm_service")
logging.basicConfig(level=logging.INFO)
# function definition for sending prompt to LLM --#
def call_llm(prompt: str, model: str = "mixtral-8x7b-32768", temperature: float = 0.2) -> str:
    """
    Call the Groq LLM API to get a response for the given prompt.

    Args:
        prompt (str): The input text for the LLM to process.
        model (str): The model to use for the response generation (default is "mixtral-8x7b-32768").
        temperature (float): The temperature to control the randomness of the response (default is 0.2).
    
    Returns:
        str: The LLM's generated response.
    """
    # Get the Groq API key from the environment variable
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY is not set.")
        return "Error: Set GROQ_API_KEY. Draft: " + prompt[:300]
# ---- try block LLm  API call----
    try:
        # Initialize Groq client with API key
        client = Groq(api_key=api_key)

        # Send request to Groq API
        response = client.chat.completions.create(
            model=model,  # Dynamic model choice
            temperature=temperature,  # Dynamic temperature
            messages=[
                {"role": "system", "content": "You are concise and helpful."},
                {"role": "user", "content": prompt}
            ]
        )

        # Extract and return the response content
        answer = response.choices[0].message.content
        logger.info(f"LLM response: {answer[:100]}...")  # Log the first 100 characters of the response
        return answer
# here we are dealing with exception handlng --#
    except Exception as e:
        # Log any exception that occurs
        logger.error(f"Error calling Groq API: {e}")
        return f"Error: Unable to get response from LLM. Reason: {e}"

