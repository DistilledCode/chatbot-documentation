## Data Scraping

#### Overview

The data scraping process involves collecting posts from the Lawyers Club India forums, including the discussion and experts sections. The process uses Python's `concurrent` module for concurrent requests and the `requests` and `bs4` libraries for HTML parsing and data extraction.

#### Data Sources

1. **Discussion Forum**: https://www.lawyersclubindia.com/forum/
2. **Experts Forum**: https://www.lawyersclubindia.com/experts/

#### Scraping Process

### Step 1: Scraping Post URLs and Titles

- **Scripts**:
  - `scrapping/discussion_detail.py`: Scrapes post titles and URLs from the discussion forum.
  - `scrapping/expert_detail.py`: Scrapes post titles and URLs from the experts forum.

- **Output**:
  - A list of post URLs and titles.
  - A `pkl` file containing bad requests (URLs that returned non-200 status codes).
  - A text file with the current offset number (number of posts scraped so far.)

### Step 2: Scraping Post Details

- **Scripts**:
  - `scrapping/discussion_posts.py`: Scrapes post details (date of reply and body of reply) from the discussion forum.
  - `scrapping/expert_posts.py`: Scrapes post details (date of reply and body of reply) from the experts forum.

- **Input**:
  - The list of post URLs generated in Step 1.

- **Output**:
  - A JSON file containing all post details.
  - A `pkl` file containing URLs that returned non-200 status codes.
  - A list of URLs of posts with multipage replies (to be implemented).

### Step 3: Combining Data and Generating Category Frequencies

- **Script**: `combine.py`

- **Input**:
  - The JSON files generated in Step 2.

- **Output**:
  - A single JSON file combining data from both forums.
  - Prints category frequency.

### Notes

- The category names printed in `combine.py` in the final step will be used to specify the category to augment questions and generate answers.
- The HTML structure of both sources is different, requiring separate scripts for each source.
- The data is dumped periodically to ensure data integrity in case of interruptions.

## Data Augmentation & Creating Embeddings

### Need for Data Augmentation

1. **Limited Context Length of LLMs**: Large Language Models (LLMs) have context length limits, which is the number of tokens they consider before generating a response. Converting a post with 500+ tokens to a QnA pair comprising only ~80-100 tokens saves a lot of context length.
2. **Consolidation of Answers**: Often, the complete answer is spread across different comments. By employing an LLM to pick up all the important points from each comment and generate a final consolidated answer, we reduce the chances of hallucination as irrelevant parts of our data have been omitted.

### Setup Before Augmentation

We will use an LLM locally and deploy it on a local server. Then, we'll send our augmentation requests over HTTP using the `requests` library. This method allows us to send multiple requests concurrently, speeding up the augmentation process. For deploying the server, we'll use the `serve` utility of the `llama.cpp` GitHub project. We will use quantized versions of LLMs instead of full-precision ones due to their increased throughput with minimal performance degradation. In our case, we're using the 4_K_M quantization of Mistral 7B v2 Instruct.

### Setting Up the Server

1. **Clone the llama.cpp Repository and Navigate to It**
    ```shell
    git clone https://github.com/ggerganov/llama.cpp
    cd llama.cpp
    ```

2. **Build the Project**
    ```shell
    make -j LLAMA_CUDA=1 LLAMA_CUDA_NVCC=/usr/local/cuda-12/bin/nvcc
    ```
    Adjust `/usr/local/cuda-12/bin/nvcc` according to your CUDA installation path.

3. **Download the GGUF Model**
    Download the GGUF of the Mistral LLM to a convenient location using the following link: [Mistral-7B-Instruct-v0.2-GGUF](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf). You may also choose a different quantization or a different LLM of your convenience. Just make sure you use the `.gguf` quantization.

4. **Starting the Server**
    Run the following script in the `llama.cpp` directory:
    ```shell
    ./server \
    -m {{path/to/our/model/mistral-7b-instruct-v0.2.Q4_K_M.gguf}} \
    -c 24000 \
    -ngl 33 \
    -cb \
    -n 5950 \
    --port 8080 \
    -np 4 \
    --threads-http 12
    ```

    **Breakdown of the Command:**
    - `-m`: Path to our model
    - `-c`: Total combined context length of all instances (also called KV Cache)
    - `-ngl`: Number of layers to be offloaded to GPU (Mistral v2 7B has 33 layers)
    - `-cb`: Continuous batching
    - `-n`: Number of max tokens for a given slot (prompt + generated tokens)
    - `-np`: Number of slots (for parallel processing)
    - `--threads-http`: Number of threads to use for serving the server

    More details can be found in the [official documentation](https://github.com/ggerganov/llama.cpp/blob/master/examples/server/README.md).

    **Calculation to Consider**: The product of `-np` and `-n` should never exceed `-c` or the server might crash when all the slots are generating the maximum allowed tokens. The context length mentioned in `-n` and `-c` is independent of the context length of the LLM used. If an LLM is capable of generating only 4k tokens and is being served with the flag `-n 10000`, it won't generate 10k tokens. It will only generate 4k tokens at max.

5. **Test the Server Using `curl`**:
    ```shell
    curl --request POST \
        --url http://localhost:8080/completion \
        --header "Content-Type: application/json" \
        --data '{"prompt": "Building a website can be done in 10 simple steps:"}'
    ```

### Augmenting the Data

Before running `augment/augment_questions.py`, you need to specify the category for which you want to augment the questions. This is done by manually editing the `CATEGORY` variable in the script at line 18 of `augment/augment_questions.py`. The `augment/augment_answers.py` script will also import the `CATEGORY` variable from `augment_questions.py`.

1. **Edit the `CATEGORY` Variable**:
    - Open `augment/augment_questions.py`.
    - Locate line 18 and set the `CATEGORY` variable to the desired category.

2. **Run the Augmentation Script**:
    - Execute the script to start augmenting the questions. The script will periodically save the augmented questions.
    ```shell
    python augment/augment_questions.py
    ```

3. **Generate Answers for Augmented Questions**:
    - Run the `augment/augment_answers.py` script to generate answers for the augmented questions. The category specified in `augment_questions.py` will be used for generating the answers as well. Ensure that the augmented questions for the specified category exist in the `/processed_data` directory.
    ```shell
    python augment/augment_answers.py
    ```

### Creating Embeddings and Pushing to Pinecone

Once the QnA pairs are augmented for all posts of a specified category, you can create embeddings of the pairs and push them to a Pinecone vector store. For embedding the QnA pairs, we are using the [BGE-M3](https://huggingface.co/BAAI/bge-m3) embedding model, a multilingual state-of-the-art model that creates 1024-dimensional vectors.

1. **Specify Pinecone API Key**:
    - Open `augment/embed_and_push.py`.
    - Locate line 12 and set your Pinecone API key.

2. **Run the Embedding and Pushing Script**:
    - Execute the script to create embeddings and push them to the Pinecone vector store in batches. All the embeddings pushed to Pinecone will contain the corresponding QnA in their metadata.
    ```shell
    python augment/embed_and_push.py
    ```
