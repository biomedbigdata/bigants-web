import json
import uuid
from os import path

import pandas as pd
from celery.result import AsyncResult
from django.core.files.base import ContentFile
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from .models import Job
from .tasks import preprocess_file_2, import_ndex, preprocess_ppi_file, \
    check_input_files, run_algorithm


class IndexView(TemplateView):
    template_name = "clustering/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['navbar'] = 'home'
        return context


class AnalysisSetupView(TemplateView):
    template_name = "clustering/analysis_setup.html"

    def get_context_data(self, **kwargs):
        # Create new session if none is found
        if not self.request.session.session_key:
            self.request.session.create()

        context = super().get_context_data(**kwargs)
        context['navbar'] = 'analysis'
        context['groupbar'] = 'setup_analysis'
        return context


@csrf_exempt  # TODO IMPORTANT REMOVE FOR PRODUCTION!!!!
def submit_analysis(request):
    """
    Parse the options and files from the given POST request (generated by AnalysisSetupView)
    and start analysis task with Celery
    """

    # TODO Debug remove
    print(f'===== POST REQUEST: {request.POST}')
    print(f'===== REQUEST FILES: {request.FILES}')

    # ========== Test if all the parameters are set correctly ==========
    # EMPTY, needs to be done

    # ========== Parse algorithm parameters from post request ==========
    session_id = None
    algorithm_parameters = dict()

    # --- Step 0: Populate session_id
    if request.user.is_authenticated:
        pass  # Add user auth here and set session_id to user
    else:
        session_id = request.session.session_key

    # --- Step 1: Expression Data
    expr_data_selection = request.POST['expression-data']
    expr_data_str = None

    # Parse expression network from uploaded file into string (easier to serialize than file object)
    if expr_data_selection == 'custom':
        expr_data_str = request.FILES['expression-data-file'].read().decode('utf-8')

    # --- Step 2: PPI Network
    ppi_network_selection = request.POST['ppi-network']
    ppi_network_str = None

    # Parse ppi network from uploaded file into string (easier to serialize than file object)
    if ppi_network_selection == 'custom':
        ppi_network_str = request.FILES['ppi-network-file'].read().decode('utf-8')

    # --- Step 3: Meta data
    survival_col_name = ''
    clinical_df = pd.DataFrame()
    use_metadata = True

    if 'use_metadata' in request.POST:
        if request.POST['use_metadata'] == 'yes':  # Set parameter for metadata analysis if desired
            print("USING METADATA")
            if 'survival-col' in request.POST and 'survival-metadata-file' in request.FILES:
                survival_col_name = request.POST['survival_col']
                clinical_df = pd.read_csv(request.FILES['survival-metadata-file'])
        else:  # Set the variables to empy, default checkbox for example data
            use_metadata = False
            pass

    algorithm_parameters['use_metadata'] = use_metadata
    algorithm_parameters['survival_col'] = survival_col_name
    algorithm_parameters['clinical_df'] = clinical_df

    # --- Step 4 (Required)
    L_g_min = int(request.POST['L_g_min'])
    L_g_max = int(request.POST['L_g_max'])

    # --- Step 4 (Optional)
    if request.POST['clustering_advanced'] == 'yes':
        nbr_iter = int(request.POST.get("nbr_iter"))  # Todo check with Olga if defaults should be set (45?)
        gene_set_size = int(request.POST.get("gene_set_size", 2000))
        nbr_ants = int(request.POST.get("nbr_ants", 30))
        evap = float(request.POST.get("evap", 0.3))
        pher_sig = float(request.POST.get("pher", 1))
        hi_sig = float(request.POST.get("hisig", 1))
        epsilon = float(request.POST.get("stopcr", 0.02))

        algorithm_parameters['size'] = gene_set_size
        algorithm_parameters['max_iter'] = nbr_iter
        algorithm_parameters['K'] = nbr_ants
        algorithm_parameters['evaporation'] = evap
        algorithm_parameters['b'] = pher_sig
        algorithm_parameters['a'] = hi_sig
        algorithm_parameters['eps'] = epsilon

    print('All the given data was parsed: Starting clustering')

    # ========== Save the task into the database (create a job) ==========
    task_id = uuid.uuid4()

    if session_id:
        job = Job(job_id=task_id, session_id=session_id, submit_time=timezone.now(), status=Job.SUBMITTED)
        job.save()
    else:
        raise KeyError('session_id not found')

    # ========== Run the clustering algorithm ==========
    print('Running algorithm started')
    # started_algorithm_id = run_algorithm.delay(job, expr_data_selection, expr_data_str, ppi_network_selection,
    #                                            ppi_network_str, False, gene_set_size, L_g_min, L_g_max, n_proc=1,
    #                                            a=hi_sig, b=pher_sig, K=nbr_ants, evaporation=evap, th=0.5, eps=epsilon,
    #                                            times=6, clusters=2, cost_limit=5, max_iter=nbr_iter, opt=None,
    #                                            show_pher=False, show_plot=False, save=None, show_nets=False).id

    run_algorithm.apply_async(args=[job, expr_data_selection, expr_data_str, ppi_network_selection, ppi_network_str,
                                    L_g_min, L_g_max, False], kw_args=algorithm_parameters, task_id=str(task_id))

    print(f'redicreting to analysis_status')
    return HttpResponseRedirect(reverse('clustering:analysis_status', kwargs={'analysis_id': task_id}))


def test(request):
    old_key = request.session.session_key
    request.session.cycle_key()
    return HttpResponse(f'old key {old_key} : new key {request.session.session_key}')


def test_result(request):
    # return render(request, 'clustering/result_single.html', context={
    #     'ppi_json': 'clustering/test/ppi.json',
    #     'heatmap_png': 'clustering/test/heatmap.png',
    #     'survival_plotly': 'clustering/test/output_plotly.html',
    #     'convergence_png': 'clustering/test/conv.png',
    # })
    pass

@csrf_exempt  # TODO IMPORTANT REMOVE FOR PRODUCTION!!!!
def poll_status(request):
    data = 'Internal failure. Please contact your administrator'
    if request.is_ajax():
        if 'task_id' in request.POST.keys() and request.POST['task_id']:
            # Retrieve task and get details
            task_id = request.POST['task_id']
            task = AsyncResult(task_id)
            task_info = task.info
            task_status = task.status
            # Create dictionary for response
            data = task_info if task_info else dict()
            data['task_status'] = task_status
        else:
            data = 'No task_id in the request found'
    else:
        data = 'This is not an ajax request'
    print(f'Response {data}')
    json_data = json.dumps(data)
    return HttpResponse(json_data, content_type='application/json')


def analysis_status(request, analysis_id):
    analysis_task = AsyncResult(str(analysis_id))
    return render(request, 'clustering/analysis_status.html', context={
        'navbar': 'analysis',
        'groupbar': 'results',
        'task': analysis_task,
    })


def analysis_result(request, analysis_id):
    job = Job.objects.get(job_id=analysis_id)
    return render(request, 'clustering/result_single.html', context={
        'navbar': 'analysis',
        'groupbar': 'results',
        'ppi_png': job.ppi_png.name,
        'ppi_json': job.ppi_json.name,
        'heatmap_png': job.heatmap_png.name,
        'survival_plotly': job.survival_plotly.name,
        'convergence_png': job.convergence_png.name,
    })


def results(request):
    session_id = request.session.session_key

    previous_jobs = Job.objects.filter(session_id__exact=session_id).order_by('-submit_time')
    return render(request, 'clustering/results.html', context={
        'navbar': 'analysis',
        'groupbar': 'all_results',
        'previous_jobs': previous_jobs
    })


class DocumentationView(TemplateView):
    template_name = 'clustering/documentation.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['navbar'] = 'documentation'
        return context


class SourcesView(TemplateView):
    template_name = 'clustering/sources.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['navbar'] = 'sources'
        return context
