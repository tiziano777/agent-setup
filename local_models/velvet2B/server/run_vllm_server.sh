ckpt="ba34086"
ckpt_path= "/nfs/training-output/velvet-cycle2/Velvet-2B-1.5/ckpt_2B_v2/huggingface/ba34086"
#ckpt_path="/nfs/training-output/velvet-cycle2/Velvet-2B-1.5/l06_f5/001_s_09_5/ba53454"
t=0.0

name="velvet-2b-1.5_${ckpt}_t${t}"

sudo docker run \
	--runtime nvidia \
	--gpus all \
	-v $ckpt_path:$ckpt_path \
	-p 8001:8001 \
	--ipc=host \
	vllm/vllm-openai:v0.10.2 \
	--model $ckpt_path \
	--served-model-name  $name \
	--generation-config auto \
	--override-generation-config {\"temperature\":$t} \
	--port 8001 \
	--gpu-memory-utilization 0.85
